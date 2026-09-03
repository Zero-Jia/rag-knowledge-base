"""P1-7: 对现有文档重建层级索引（reindex 脚本），激活 auto_merge（Small-to-Big）。

背景：现有文档均在 HIERARCHICAL_CHUNKING_ENABLED 生效前用 non-hierarchy 路径入库，
ParentChunk 表 0 行、向量库 metadata 无层级字段，auto_merge 永远不触发
（验证见 scripts/verify_auto_merge_p1_7.py）。
本脚本对 status=DONE 的文档逐个重跑 index_document_pipeline：
当前配置 HIERARCHICAL_CHUNKING_ENABLED=True，重跑即走层级分块路径——
写 ParentChunk 表（L1/L2）+ L3 leaf 连同层级 metadata 重建向量库。

用法：
    python scripts/reindex_hierarchy_p1_7.py
可选环境变量：
    REINDEX_DOC_IDS=7,8   只重建指定文档（默认全部 status=DONE）

注意：
- 会删除并重建每个文档的向量数据（文档级幂等，重跑安全）
- L3 leaf chunk_id 规则与 non-hierarchy 相同（doc{id}_chunk{i}），citations 兼容
- 评估 gold_chunks 按 keywords 匹配 text，不依赖 chunk_id，评估兼容
- 失败文档（status=FAILED）自动跳过（pipeline 内部同样跳过）
"""
import os
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.document import Document, DocumentStatus  # noqa: E402
from app.models.parent_chunk import ParentChunk  # noqa: E402
from app.services.indexing_service import index_document_pipeline  # noqa: E402


def main() -> None:
    print(f"HIERARCHICAL_CHUNKING_ENABLED = {settings.HIERARCHICAL_CHUNKING_ENABLED}")
    if not settings.HIERARCHICAL_CHUNKING_ENABLED:
        print("[reindex] 层级分块未开启，重建仍会走 non-hierarchy 路径，退出")
        return

    doc_ids_env = os.getenv("REINDEX_DOC_IDS", "").strip()
    db = SessionLocal()
    try:
        query = db.query(Document).filter(Document.status == DocumentStatus.DONE)
        if doc_ids_env:
            wanted = [int(x) for x in doc_ids_env.split(",") if x.strip()]
            query = query.filter(Document.id.in_(wanted))
        docs = query.all()
        print(f"[reindex] 待重建文档: {[d.id for d in docs]}")

        for doc in docs:
            print(f"[reindex] doc_id={doc.id} start | file={doc.file_path}")
            index_document_pipeline(doc.id)
            # pipeline 内部独立 session 提交，这里重查状态与父块数
            db.expire_all()
            fresh = db.query(Document).filter(Document.id == doc.id).first()
            parent_count = (
                db.query(ParentChunk).filter(ParentChunk.document_id == doc.id).count()
            )
            print(
                f"[reindex] doc_id={doc.id} done | status={fresh.status} "
                f"| parent_chunks={parent_count}"
            )

        total = db.query(ParentChunk).count()
        print(f"[reindex] 全部完成，ParentChunk 表总行数 = {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
