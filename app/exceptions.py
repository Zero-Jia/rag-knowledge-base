from typing import Any, Optional

class AppError(Exception):
    """
    业务可控异常：
    - 只能在 service 层抛出
    - router 不做业务判断
    - 由全局 handler 统一转成 APIResponse
    """
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Any] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)
