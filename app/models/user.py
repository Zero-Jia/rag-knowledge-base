# （ORM 表）
from sqlalchemy import String,Integer
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base

class User(Base):
    # __tablename__：这张表在数据库里的表名
    __tablename__="users"

    # mapped_column：把“类属性”映射成“数据库列”
    id:Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    # unique=True：强制唯一（防止两个用户同名/同邮箱）
    username: Mapped[str] = mapped_column(String,unique=True,index=True)
    email: Mapped[str] = mapped_column(String,unique=True,index=True)
    password: Mapped[str] = mapped_column(String)