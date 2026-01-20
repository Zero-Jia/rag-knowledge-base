# Document ORM 模型
from sqlalchemy import Integer,String,ForeignKey,DateTime
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime

from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id:Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    user_id:Mapped[int] = mapped_column(Integer,ForeignKey("users.id"),index=True)
    filename:Mapped[str] = mapped_column(String)
    file_path:Mapped[str] = mapped_column(String)
    content_type:Mapped[str] = mapped_column(String)
    created_at:Mapped[DateTime] = mapped_column(DateTime,default=datetime.utcnow)