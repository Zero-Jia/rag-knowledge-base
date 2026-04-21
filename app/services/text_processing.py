from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings


@dataclass
class HierarchicalChunk:
    """
    Structured chunk used by hierarchical RAG.

    L1/L2 are parent chunks and are stored in SQL.
    L3 chunks are retrieval leaves and are embedded into the vector store.
    """

    chunk_id: str
    text: str
    chunk_level: int
    chunk_index: int
    parent_chunk_id: Optional[str]
    root_chunk_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HierarchicalChunkSet:
    """
    Output compatible with the existing indexing flow.

    indexing_service can store `parent_chunks` in SQL and embed `leaf_chunks`
    into Chroma by reading each chunk's `text`, `chunk_id`, and `metadata`.
    """

    parent_chunks: List[HierarchicalChunk]
    leaf_chunks: List[HierarchicalChunk]


def clean_text(text: str) -> str:
    """
    Basic text cleanup:
    - normalize line endings
    - collapse 3+ blank lines into 2
    - collapse repeated spaces/tabs
    - trim leading/trailing whitespace
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = settings.CHUNK_SIZE,
    overlap: int = settings.CHUNK_OVERLAP,
) -> List[str]:
    """
    Fixed-size chunking with overlap.

    This function intentionally remains simple because it is also used by the
    old preview/indexing path. Hierarchical chunking composes this primitive.
    """
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")

    chunks: List[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()

        if len(chunk) >= settings.CHUNK_MIN_LENGTH:
            chunks.append(chunk)

        if end == text_length:
            break

        next_start = end - overlap
        if next_start <= start:
            break
        start = next_start

    return chunks


def process_text(
    raw_text: str,
    chunk_size: int = settings.CHUNK_SIZE,
    overlap: int = settings.CHUNK_OVERLAP,
) -> List[str]:
    """
    Backward-compatible text processing entrypoint.

    Existing callers still receive `List[str]`.
    """
    cleaned = clean_text(raw_text)
    return chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)


def _chunk_id(document_id: int, level: int, *parts: int) -> str:
    suffix = "_".join(str(part) for part in parts)
    return f"doc{document_id}_l{level}_{suffix}"


def _leaf_chunk_id(document_id: int, chunk_index: int) -> str:
    return f"doc{document_id}_chunk{chunk_index}"


def _base_metadata(
    *,
    document_id: int,
    user_id: int,
    chunk_id: str,
    chunk_level: int,
    chunk_index: int,
    parent_chunk_id: Optional[str],
    root_chunk_id: str,
    text: str,
) -> Dict[str, Any]:
    return {
        "document_id": document_id,
        "user_id": user_id,
        "chunk_id": chunk_id,
        "chunk_level": chunk_level,
        "chunk_index": chunk_index,
        "parent_chunk_id": parent_chunk_id,
        "root_chunk_id": root_chunk_id,
        "text_length": len(text),
    }


def process_text_hierarchy(
    raw_text: str,
    *,
    document_id: int,
    user_id: int,
) -> HierarchicalChunkSet:
    """
    Build a 3-level parent-child chunk tree.

    Output:
    - L1 chunks: large root parent chunks
    - L2 chunks: medium parent chunks under L1
    - L3 chunks: small retrieval leaves under L2

    Storage contract:
    - `parent_chunks` contains L1/L2 for SQL storage.
    - `leaf_chunks` contains L3 for embedding and vector storage.
    """
    cleaned = clean_text(raw_text)
    if not cleaned:
        return HierarchicalChunkSet(parent_chunks=[], leaf_chunks=[])

    l1_texts = chunk_text(
        cleaned,
        chunk_size=settings.HIERARCHICAL_L1_CHUNK_SIZE,
        overlap=settings.HIERARCHICAL_L1_CHUNK_OVERLAP,
    )

    parent_chunks: List[HierarchicalChunk] = []
    leaf_chunks: List[HierarchicalChunk] = []
    global_leaf_index = 0

    for l1_index, l1_text in enumerate(l1_texts):
        l1_chunk_id = _chunk_id(document_id, 1, l1_index)
        l2_texts = chunk_text(
            l1_text,
            chunk_size=settings.HIERARCHICAL_L2_CHUNK_SIZE,
            overlap=settings.HIERARCHICAL_L2_CHUNK_OVERLAP,
        )

        l1_metadata = _base_metadata(
            document_id=document_id,
            user_id=user_id,
            chunk_id=l1_chunk_id,
            chunk_level=1,
            chunk_index=l1_index,
            parent_chunk_id=None,
            root_chunk_id=l1_chunk_id,
            text=l1_text,
        )
        l1_metadata.update(
            {
                "child_count": len(l2_texts),
                "l2_count": len(l2_texts),
            }
        )

        parent_chunks.append(
            HierarchicalChunk(
                chunk_id=l1_chunk_id,
                text=l1_text,
                chunk_level=1,
                chunk_index=l1_index,
                parent_chunk_id=None,
                root_chunk_id=l1_chunk_id,
                metadata=l1_metadata,
            )
        )

        for l2_index, l2_text in enumerate(l2_texts):
            l2_chunk_id = _chunk_id(document_id, 2, l1_index, l2_index)
            l3_texts = chunk_text(
                l2_text,
                chunk_size=settings.HIERARCHICAL_L3_CHUNK_SIZE,
                overlap=settings.HIERARCHICAL_L3_CHUNK_OVERLAP,
            )

            l2_metadata = _base_metadata(
                document_id=document_id,
                user_id=user_id,
                chunk_id=l2_chunk_id,
                chunk_level=2,
                chunk_index=l2_index,
                parent_chunk_id=l1_chunk_id,
                root_chunk_id=l1_chunk_id,
                text=l2_text,
            )
            l2_metadata.update(
                {
                    "child_count": len(l3_texts),
                    "l3_count": len(l3_texts),
                    "root_child_count": len(l2_texts),
                    "l1_index": l1_index,
                }
            )

            parent_chunks.append(
                HierarchicalChunk(
                    chunk_id=l2_chunk_id,
                    text=l2_text,
                    chunk_level=2,
                    chunk_index=l2_index,
                    parent_chunk_id=l1_chunk_id,
                    root_chunk_id=l1_chunk_id,
                    metadata=l2_metadata,
                )
            )

            for l3_index, l3_text in enumerate(l3_texts):
                l3_chunk_id = _leaf_chunk_id(document_id, global_leaf_index)
                l3_metadata = _base_metadata(
                    document_id=document_id,
                    user_id=user_id,
                    chunk_id=l3_chunk_id,
                    chunk_level=3,
                    chunk_index=global_leaf_index,
                    parent_chunk_id=l2_chunk_id,
                    root_chunk_id=l1_chunk_id,
                    text=l3_text,
                )
                l3_metadata.update(
                    {
                        "l1_index": l1_index,
                        "l2_index": l2_index,
                        "sibling_index": l3_index,
                        "sibling_count": len(l3_texts),
                        "root_child_count": len(l2_texts),
                    }
                )

                leaf_chunks.append(
                    HierarchicalChunk(
                        chunk_id=l3_chunk_id,
                        text=l3_text,
                        chunk_level=3,
                        chunk_index=global_leaf_index,
                        parent_chunk_id=l2_chunk_id,
                        root_chunk_id=l1_chunk_id,
                        metadata=l3_metadata,
                    )
                )
                global_leaf_index += 1

    return HierarchicalChunkSet(
        parent_chunks=parent_chunks,
        leaf_chunks=leaf_chunks,
    )
