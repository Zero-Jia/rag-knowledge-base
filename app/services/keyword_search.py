# 实现关键词匹配得分
import re
def keyword_score(text:str,query:str)->float:
    """
    简单关键词匹配得分：
    - query 分词后（粗暴 token）
    - text 里每命中一个 token +1
    - 追求：工程可控、可解释、好实现
    """
    if not text or not query:
        return 0.0
    
    tokens = re.findall(r"\w+",query.lower())
    if not tokens:
        return 0.0
    
    text_lower = text.lower()

    score = 0.0
    for token in tokens:
        if token in text_lower:
            score+=1.0

    return score