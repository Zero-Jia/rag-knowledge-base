# Document ORM 模型
import enum
from sqlalchemy import Integer,String,ForeignKey,DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime

from app.database import Base

class DocumentStatus(enum.Enum):
    # pending：刚上传，尚未索引
    # processing：后台正在 parse/chunk/embedding/入库
    # done：索引完成，可检索
    # failed：索引失败，需要重试/排查
    PENDING = "pending"  
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"

class Document(Base):
    __tablename__ = "documents"

    id:Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    user_id:Mapped[int] = mapped_column(Integer,ForeignKey("users.id"),index=True)
    filename:Mapped[str] = mapped_column(String)
    file_path:Mapped[str] = mapped_column(String)
    content_type:Mapped[str] = mapped_column(String)
    created_at:Mapped[DateTime] = mapped_column(DateTime,default=datetime.utcnow)

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus),
        default=DocumentStatus.PENDING,
        nullable=False,
        index = True,
    )

    created_at:Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow)