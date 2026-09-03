"""
P1-2：三层漏斗路由的第一层 —— 规则脚本前置路由。

detect_complex_query 用确定性规则识别"明显复杂"的问题（多意图 / 比较 /
并列子句），命中即建议前置升级到 ReAct agent。

设计原则（保守、高精度）：
- 宁可漏判（后置证据升级兜底），不可误判（简单问题送 ReAct 的成本是
  延迟 3-5 倍、token 翻数倍）；
- 纯函数、零 token、零延迟、可单测；
- 单问号的"有哪些/是什么"枚举类单意图问题、followup 追问一律不命中。
"""
from __future__ import annotations

import re
from typing import Tuple

# 比较/对比句式信号词
_COMPARE_WORDS = re.compile(r"(区别|差异|对比|比较|相比|优缺点|各自|分别)")

# 并列实体连接词（与比较词共现时构成比较句式）
_COMPARE_CONNECTORS = re.compile(r"(和|与|跟|以及)")

# 并列子句连接词（连接多个独立分句时构成多意图）
_PARALLEL_CLAUSE_CONNECTORS = ("同时", "另外", "还有", "顺便", "此外")

# 分句切分：中英文标点
_CLAUSE_SPLIT = re.compile(r"[？?。；;，,、\s]+")

# 一个"有效分句"的最小长度（短于该长度视为语气词/指代片段，不计入）
_MIN_CLAUSE_LEN = 4


def _split_clauses(question: str) -> list:
    return [c.strip() for c in _CLAUSE_SPLIT.split(question) if len(c.strip()) >= _MIN_CLAUSE_LEN]


def detect_complex_query(question: str) -> Tuple[bool, str]:
    """
    规则脚本：判断问题是否为明显复杂问题（建议前置升级 ReAct）。

    返回 (hit, reason)：
    - hit=True 时 reason 为命中规则标识（rule_*）；
    - hit=False 时 reason 为空字符串。
    """
    q = (question or "").strip()
    if not q:
        return False, ""

    # 规则 1：多个问号 —— 几乎必然是多个子问题
    question_marks = q.count("？") + q.count("?")
    if question_marks >= 2:
        return True, "rule_multi_question_mark"

    # 规则 2：比较句式 —— 比较词 + 并列连接词共现
    # 例："HyDE 和 step-back 分别在什么场景用？"
    if _COMPARE_WORDS.search(q) and _COMPARE_CONNECTORS.search(q):
        return True, "rule_comparison"

    # 规则 3：并列子句 —— 并列连接词连接 >=2 个有效分句
    # 例："缓存分哪几种？另外语义缓存用的什么模型？"
    clauses = _split_clauses(q)
    if len(clauses) >= 2:
        for connector in _PARALLEL_CLAUSE_CONNECTORS:
            if connector in q:
                return True, f"rule_parallel_clause:{connector}"

    return False, ""
