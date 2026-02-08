# 文档响应
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentOut(BaseModel):
    id: int = Field(..., description="Document ID")
    filename: str = Field(..., description="Original uploaded filename")
    created_at: datetime = Field(..., description="Document upload time")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "filename": "deep_learning_intro.pdf",
                    "created_at": "2026-02-01T10:23:45"
                }
            ]
        }
    }

    class Config:
        orm_mode = True
