# 新增登录接口
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    summary="User login (OAuth2 password flow)",
    description=(
        "Authenticate user using OAuth2 password flow and return a JWT access token.\n\n"
        "- Accepts form fields: `username` and `password`\n"
        "- On success, returns `access_token` and `token_type`\n"
        "- The token should be sent in header: `Authorization: Bearer <token>`"
    ),
    responses={
        200: {
            "description": "Login success",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6MTc3MDIwNzI4NX0.xxxxxxxxxxxxx",
                        "token_type": "bearer",
                    }
                }
            },
        },
        400: {
            "description": "Incorrect username or password",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Incorrect username or password"
                    }
                }
            },
        },
        422: {
            "description": "Validation error (missing form fields)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "missing",
                                "loc": ["body", "username"],
                                "msg": "Field required",
                                "input": None,
                            }
                        ]
                    }
                }
            },
        },
    },
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 标准登录流程：
    - 接收表单字段 username / password
    - 校验用户名是否存在
    - 使用 verify_password 校验密码
    - 使用 create_access_token 生成 JWT
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password",
        )

    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password",
        )

    token = create_access_token({"sub": user.username})

    return {
        "access_token": token,
        "token_type": "bearer",
    }
