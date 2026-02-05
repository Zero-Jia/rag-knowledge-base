# 统一日志配置（全局总开关）
import logging
import sys

def setup_logging():
    """
    全局日志配置：统一格式 + 统一等级
    - 不再用 print
    - 让关键路径日志一眼可读
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # 可选：压掉一些第三方库太吵的日志
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)