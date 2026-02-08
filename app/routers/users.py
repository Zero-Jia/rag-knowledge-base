# 写 users router（REST + 校验 + 业务错误）
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.models.user import User
from app.database import get_db
from app.security import get_current_user, get_password_hash

# prefix="/users"：这个文件里所有接口都统一以 /users 开头
# tags=["users"]：Swagger /docs 里会分组显示
router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/",
    summary="Create a new user",
    description=(
        "Register a new user account.\n\n"
        "- No authentication required\n"
        "- Username must be unique\n"
        "- Password will be hashed before storing in database"
    ),
    responses={
        200: {
            "description": "User created",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "username": "alice",
                        "email": "alice@example.com",
                    }
                }
            },
        },
        400: {
            "description": "Username already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Username already exists"
                    }
                }
            },
        },
    },
)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    """
    创建用户
    """
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    # ✅ 核心改动：把明文密码先 hash 再存库
    hashed_password = get_password_hash(user.password)

    db_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "id": db_user.id,
        "username": db_user.username,
        "email": db_user.email,
    }


@router.get(
    "/me",
    summary="Get current user profile",
    description=(
        "Return profile information of the currently authenticated user.\n\n"
        "- Auth required\n"
        "- Uses JWT access token from `Authorization` header"
    ),
    responses={
        200: {
            "description": "Current user profile",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "username": "alice",
                        "email": "alice@example.com",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            },
        },
    },
)
def read_me(
    current_user=Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
    }
