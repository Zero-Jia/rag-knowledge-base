# 自定义异常

class AppError(Exception):
    """
    业务可控异常：service 层随时可 raise AppError(...)
    由全局 handler 统一转成标准 JSON
    """
    def __init__(self,code:str,message:str,status_code:int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code