from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,DeclarativeBase

# 数据库地址: 告诉 ORM,"用 SQLite, 数据库存成一个文件"
DATABASE_URL = "sqlite:///./rag.db"

# engine：数据库连接（SQLite 就是一个文件）
# engine（连接入口）。engine 是 SQLAlchemy 的数据库“连接管理器”
# SQLite 在多线程 Web 环境下必须关闭线程检查
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread":False}, # SQLite 必须
)

# SessionLocal()：创建一次会话（一次请求用一次）
# SessionLocal（会话工厂）
# 定义“如何创建 Session”。不自动提交，避免误写库；不自动 flush，保持行为可控
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Base（ORM 根类）
# 所有 ORM 表必须继承它，SQLAlchemy 通过它收集表结构信息
class Base(DeclarativeBase):
    pass

# get_db()：FastAPI 用 yield 管理生命周期，请求结束自动 close
# get_db（Session 生命周期）
# 请求开始 → 创建 Session
# 请求结束 → 自动关闭
def get_db()->Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()