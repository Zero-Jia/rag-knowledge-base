# 密码 hash + JWT + 当前用户
from datetime import datetime,timedelta
from typing import Optional

from fastapi import Depends,HTTPException,status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt,JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.config import settings

# 1) 密码 hash 上下文：指定算法 bcrypt
pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")
# 2) OAuth2 的“拿 token 的地址”
#    注意：tokenUrl 要指向你的登录接口路径
oauto2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# -------------------------
# A. 密码相关：hash & verify
# -------------------------
def get_password_hash(password:str)->str:
    """
    把明文密码 -> hash（不可逆）
    """
    return pwd_context.hash(password)

def verify_password(plain_password:str,hashed_password:str)->bool:
    """
    校验：用户输入的明文密码 是否匹配 数据库里的 hash
    """
    return pwd_context.verify(plain_password,hashed_password)

# -------------------------
# B. JWT 相关：创建 token
# -------------------------
def create_access_token(data:dict,expires_delta:Optional[timedelta]=None)->str:
    """
    data: 通常放身份标识，例如 {"sub": username}
    expires_delta: 可自定义过期时间；不传就用配置里的分钟数
    """
    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    
    expires = datetime.utcnow()+expires_delta
    to_encode.update({"exp":expires})

    encode_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encode_jwt

# -------------------------
# C. 认证相关：解析 token -> 得到 current_user
# -------------------------
def get_current_user(
    token:str = Depends(oauto2_scheme),
    db:Session = Depends(get_db),
)->User:
    """
    这是“受保护接口”的关键：
    - 从请求头 Authorization: Bearer <token> 拿到 token
    - 解码 token 验签
    - 取出 sub（用户名）
    - 去数据库查用户
    - 返回 user（供接口使用）
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        username:Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user