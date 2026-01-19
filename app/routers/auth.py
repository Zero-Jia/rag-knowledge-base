# 新增登录接口
from fastapi import APIRouter,Depends,HTTPException,status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import verify_password,create_access_token

router = APIRouter(prefix = "/auth",tags=["auth"])

@router.post("/login")
def login(form_data:OAuth2PasswordRequestForm = Depends(),db:Session = Depends(get_db) ):
    """
    OAuth2 标准登录：
    - 接收表单字段 username/password
    - 校验用户名是否存在
    - verify_password 校验密码
    - create_access_token 生成 JWT
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    if not verify_password(form_data.password,user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    token = create_access_token({"sub":user.username})
    return {"access_token":token,"token_type":"bearer"}
