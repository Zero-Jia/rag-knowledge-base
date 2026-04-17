from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息内容")


class AgentChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="当前用户问题")
    session_id: Optional[str] = Field(None, description="会话ID，可选")
    chat_history: List[ChatHistoryMessage] = Field(default_factory=list, description="历史对话")
    top_k: int = Field(5, ge=1, le=20, description="检索 top_k")
    rerank_top_n: int = Field(3, ge=1, le=10, description="rerank 保留条数")
    rerank_score_threshold: float = Field(0.1, description="触发 fallback 的 rerank 分数阈值")