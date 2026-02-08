# 写用户请求模型（Pydantic 校验）
# Pydantic BaseModel 定义“请求体的数据结构 + 校验规则”
# EmailStr 自动校验 email 格式（不合法会直接 422）

from pydantic import BaseModel, EmailStr, Field


# UserCreate 表示“创建用户时客户端要传什么”
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, description="Unique username")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, max_length=64, description="Plain password (will be hashed)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "alice",
                    "email": "alice@example.com",
                    "password": "123456"
                },
                {
                    "username": "bob",
                    "email": "bob@gmail.com",
                    "password": "securePass123"
                }
            ]
        }
    }
