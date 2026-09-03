"""
P3-3：PII 出站脱敏服务。

应用出口（只做出站掩码，不改 DB 存储——chat_messages 原文保留，便于回溯）：
①Langfuse trace 上报（兑现 P0-5"不上报原文 chunk 全文，为 PII 脱敏预留"的钩子）；
②后端关键日志（error/warning 中拼接的异常文本可能夹带用户输入片段）。

开关 ``settings.PII_MASK_ENABLED=True``（默认开启）；掩码过程任何异常
保守放行原文，绝不影响主流程。
"""
from __future__ import annotations

import re
from typing import Match

from app.core.config import settings

# 中国大陆手机号：1[3-9] 开头共 11 位（前后不能是数字，避免从长数字串中误截）
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

# 邮箱
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# 18 位身份证（末位可为 X/x）
_ID18 = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")

# 15 位旧版身份证
_ID15 = re.compile(r"(?<!\d)\d{15}(?!\d)")


def _keep_edges(match: Match, head: int, tail: int) -> str:
    """保留前 head 位与后 tail 位，中间用定长 * 掩码（总长不变）。"""
    s = match.group(0)
    middle = max(0, len(s) - head - tail)
    return s[:head] + "*" * middle + (s[-tail:] if tail else "")


def mask_pii(text: str) -> str:
    """
    对文本中的常见 PII 做出站掩码：
    - 手机号：138****5678（保留前 3 后 4）
    - 邮箱：a***@domain.com（保留 local 首字符）
    - 身份证：110***********2X（18 位保留前 3 后 2；15 位保留前 3 后 2）

    非字符串输入原样返回；开关关闭原样返回；异常保守放行。
    """
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ""

    if not settings.PII_MASK_ENABLED:
        return text

    try:
        text = _ID18.sub(lambda m: _keep_edges(m, 3, 2), text)
        text = _ID15.sub(lambda m: _keep_edges(m, 3, 2), text)
        # 手机号需在身份证之后处理（11 位模式不会命中 18 位段，
        # 因 lookaround 要求前后非数字）
        text = _PHONE.sub(lambda m: _keep_edges(m, 3, 4), text)
        text = _EMAIL.sub(
            lambda m: m.group(0)[0] + "***@" + m.group(0).partition("@")[2],
            text,
        )
        return text
    except Exception:
        return text
