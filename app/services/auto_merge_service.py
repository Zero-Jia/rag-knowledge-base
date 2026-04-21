from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.parent_chunk import ParentChunk


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _best_score(items: Iterable[Dict[str, Any]]) -> float:
    return max((_safe_float(item.get("score"), 0.0) for item in items), default=0.0)


def _should_merge(hit_count: int, child_count: int) -> bool:
    if hit_count <= 0:
        return False
    if hit_count >= settings.AUTO_MERGE_MIN_CHILDREN:
        return True
    if child_count <= 0:
        return False
    return (hit_count / child_count) >= settings.AUTO_MERGE_PARENT_RATIO


def _load_parent_chunks(db: Session, chunk_ids: Iterable[str]) -> Dict[str, ParentChunk]:
    ids = [chunk_id for chunk_id in dict.fromkeys(chunk_ids) if chunk_id]
    if not ids:
        return {}

    rows = db.query(ParentChunk).filter(ParentChunk.chunk_id.in_(ids)).all()
    return {row.chunk_id: row for row in rows}


def _row_to_result(
    row: ParentChunk,
    *,
    score: float,
    merged_child_count: int,
    source_level: int,
) -> Dict[str, Any]:
    metadata = dict(row.metadata_json or {})
    result: Dict[str, Any] = {
        "text": row.text,
        "document_id": row.document_id,
        "chunk_index": row.chunk_index,
        "score": float(score),
        "chunk_id": row.chunk_id,
        "chunk_level": row.chunk_level,
        "parent_chunk_id": row.parent_chunk_id,
        "root_chunk_id": row.root_chunk_id,
        "auto_merged": True,
        "merged_child_count": int(merged_child_count),
        "merged_from_level": int(source_level),
    }
    result.update(
        {
            "parent_child_count": metadata.get("child_count"),
            "root_child_count": metadata.get("root_child_count"),
        }
    )
    return result


def _merge_l3_to_l2(
    chunks: List[Dict[str, Any]],
    parent_rows: Dict[str, ParentChunk],
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in chunks:
        if _safe_int(item.get("chunk_level"), 3) == 3 and item.get("parent_chunk_id"):
            groups[str(item["parent_chunk_id"])].append(item)

    merge_ids: set[str] = set()
    for parent_id, children in groups.items():
        child_count = _safe_int(children[0].get("sibling_count"), 0)
        if _should_merge(len(children), child_count) and parent_id in parent_rows:
            merge_ids.add(parent_id)

    if not merge_ids:
        return chunks

    emitted: set[str] = set()
    merged: List[Dict[str, Any]] = []
    for item in chunks:
        parent_id = item.get("parent_chunk_id")
        if parent_id in merge_ids:
            if parent_id in emitted:
                continue
            children = groups[str(parent_id)]
            merged.append(
                _row_to_result(
                    parent_rows[str(parent_id)],
                    score=_best_score(children),
                    merged_child_count=len(children),
                    source_level=3,
                )
            )
            emitted.add(str(parent_id))
            continue
        merged.append(item)

    return merged


def _merge_l2_to_l1(
    chunks: List[Dict[str, Any]],
    parent_rows: Dict[str, ParentChunk],
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in chunks:
        if _safe_int(item.get("chunk_level"), 3) == 2 and item.get("root_chunk_id"):
            groups[str(item["root_chunk_id"])].append(item)

    merge_ids: set[str] = set()
    for root_id, children in groups.items():
        child_count = _safe_int(children[0].get("root_child_count"), 0)
        if _should_merge(len(children), child_count) and root_id in parent_rows:
            merge_ids.add(root_id)

    if not merge_ids:
        return chunks

    emitted: set[str] = set()
    merged: List[Dict[str, Any]] = []
    for item in chunks:
        root_id = item.get("root_chunk_id")
        if root_id in merge_ids and _safe_int(item.get("chunk_level"), 3) == 2:
            if root_id in emitted:
                continue
            children = groups[str(root_id)]
            merged.append(
                _row_to_result(
                    parent_rows[str(root_id)],
                    score=_best_score(children),
                    merged_child_count=len(children),
                    source_level=2,
                )
            )
            emitted.add(str(root_id))
            continue
        merged.append(item)

    return merged


def auto_merge_chunks(
    chunks: List[Dict[str, Any]],
    *,
    top_k: Optional[int] = None,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """
    Replace dense sibling leaf hits with their parent chunk when enough siblings
    match. This preserves the public result shape while giving the answer stage
    broader context.
    """
    if not settings.AUTO_MERGE_ENABLED or not chunks:
        return chunks

    owns_session = db is None
    session = db or SessionLocal()

    try:
        parent_ids = [
            str(item["parent_chunk_id"])
            for item in chunks
            if item.get("parent_chunk_id") and _safe_int(item.get("chunk_level"), 3) == 3
        ]
        root_ids = [str(item["root_chunk_id"]) for item in chunks if item.get("root_chunk_id")]
        parent_rows = _load_parent_chunks(session, parent_ids + root_ids)

        merged = _merge_l3_to_l2(chunks, parent_rows)
        merged = _merge_l2_to_l1(merged, parent_rows)

        max_chars = settings.AUTO_MERGE_MAX_PARENT_CHARS
        for item in merged:
            text = item.get("text")
            if isinstance(text, str) and max_chars > 0 and len(text) > max_chars:
                item["text"] = text[:max_chars]
                item["truncated"] = True

        if top_k is not None:
            return merged[:top_k]
        return merged
    finally:
        if owns_session:
            session.close()
