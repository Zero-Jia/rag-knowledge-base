"""
P0-4: 给现有 Chroma chunks 一次性回填 user_id metadata（reindex 脚本）

背景：现有向量数据走 non-hierarchy 路径入库，metadata 只有 document_id/chunk_index，
没有 user_id。P0-3 检索加 where={"user_id": user_id} 过滤后，旧数据会被过滤空。
本脚本遍历所有 chunk，按 document_id 查 Document 表拿 user_id，回填到 Chroma metadata。

用法：
    python scripts/reindex_user_metadata.py

注意：
- 不会重新 embedding，只更新 metadata（collection.update）
- 保留原 metadata 字段，仅追加 user_id
- 幂等：重复运行只会覆盖 user_id 为相同值
"""
import sys
from collections import defaultdict

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.document import Document
from app.services.vector_store import VectorStore


def main() -> None:
    store = VectorStore()
    db = SessionLocal()

    try:
        # 拉取全部 chunks（limit 取大值确保全量）
        payload = store.get_texts(limit=100000)
        ids = payload.get("ids", []) or []
        metadatas = payload.get("metadatas", []) or []

        print(f"[reindex] total chunks = {len(ids)}")
        if not ids:
            print("[reindex] no chunks, exit")
            return

        # 统计已带 user_id 的数量（幂等检查）
        already_has = sum(1 for m in metadatas if m.get("user_id") is not None)
        print(f"[reindex] chunks already with user_id = {already_has}")

        # 按 document_id 分组，查 Document 表拿 user_id
        doc_ids = set()
        for m in metadatas:
            did = m.get("document_id")
            if did is not None:
                try:
                    doc_ids.add(int(did))
                except (TypeError, ValueError):
                    continue

        doc_to_user = {}
        unknown_docs = []
        for d in doc_ids:
            doc = db.query(Document).filter(Document.id == d).first()
            if doc is not None:
                doc_to_user[d] = doc.user_id
            else:
                unknown_docs.append(d)

        if unknown_docs:
            print(f"[reindex] WARN: documents not found in DB: {unknown_docs}")

        print(f"[reindex] documents resolved = {len(doc_to_user)}")
        print(f"[reindex] user_id distribution = {dict(__count_users(doc_to_user))}")

        new_metadatas = []
        update_ids = []
        for cid, meta in zip(ids, metadatas):
            did = meta.get("document_id")
            try:
                did_int = int(did) if did is not None else None
            except (TypeError, ValueError):
                did_int = None
            uid = doc_to_user.get(did_int) if did_int is not None else None
            if uid is None:
                # 找不到对应 document / user_id，跳过（保留原 metadata）
                continue
            new_meta = dict(meta)
            new_meta["user_id"] = uid
            new_metadatas.append(new_meta)
            update_ids.append(cid)

        print(f"[reindex] chunks to update = {len(update_ids)}")
        if not update_ids:
            print("[reindex] nothing to update, exit")
            return

        store.update_metadatas(update_ids, new_metadatas)
        print(f"[reindex] done, updated {len(update_ids)} chunks with user_id metadata")

        # 校验：取前 3 个看 metadata
        verify = store.get_texts(limit=3)
        for m in (verify.get("metadatas") or [])[:3]:
            print("[reindex] verify:", m)
    finally:
        db.close()


def __count_users(doc_to_user):
    counts = {}
    for uid in doc_to_user.values():
        counts[uid] = counts.get(uid, 0) + 1
    return sorted(counts.items())


if __name__ == "__main__":
    main()
