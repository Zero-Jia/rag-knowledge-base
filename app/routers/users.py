# 写 users router（REST + 校验 + 业务错误）
from fastapi import APIRouter,HTTPException,Depends
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate
from app.models.user import User
from app.database import get_db
from app.security import get_current_user,get_password_hash

# prefix="/users"：这个文件里所有接口都统一以 /users 开头
# tags=["users"]：Swagger /docs 里会分组显示
router = APIRouter(prefix="/users",tags=["users"])

# @router.post("/")：最终路径是 POST /users/
@router.post("/")
# user: UserCreate：请求体必须符合 schema，否则自动 422
def create_user(user:UserCreate,db:Session = Depends(get_db)):
    """
    创建用户
    """
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # ✅ 核心改动：把明文密码先 hash 再存库.数据库泄露也拿不到明文密码。
    hashed_password = get_password_hash(user.password)
    
    db_user = User(
        username=user.username,
        email = user.email,
        password = hashed_password,
    )
    db.add(db_user)
    # commit()：把这次事务真正写入数据库
    db.commit()
    # refresh()：把数据库生成的字段（比如自增 id）刷新回对象
    db.refresh(db_user)
    return{
        "id":db_user.id,
        "username":db_user.username,
        "email":db_user.email,
    }

# /users/me：只要依赖 get_current_user，就变成“必须携带有效 token 才能访问”。
@router.get("/me")
def read_me(current_user = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
    }
