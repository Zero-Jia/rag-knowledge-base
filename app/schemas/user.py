# 写用户请求模型（Pydantic 校验）
# Pydantic BaseModel 定义“请求体的数据结构 + 校验规则”
# EmailStr 自动校验 email 格式（不合法会直接 422）
from pydantic import BaseModel,EmailStr

# UserCreate 表示“创建用户时客户端要传什么”
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str