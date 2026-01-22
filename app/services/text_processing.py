import re
from typing import List

def clean_text(text:str)->str:
    """
    基础文本清洗（稳定 + 可控）：
    - 统一换行
    - 去掉连续空行（>=3 行 -> 2 行）
    - 合并多空格/多 tab
    - 去掉首尾空白
    """
    if not text:
        return ""
    # 统一换行符
    text = text.replace("\r\n","\n").replace("\r","\n")
    # 去掉连续空行（3个及以上 -> 2个）
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 合并多个空格 / tab
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()

def chunk_text(text:str,chunk_size:int=500,overlap:int = 100)->List[str]:
    """
    固定长度分块 + overlap
    - chunk_size: 每块长度（字符数）
    - overlap: 相邻块的重叠长度（字符数）
    """
    if not text:
        return []
    if chunk_size<=0:
        raise ValueError("chunk_size must be > 0")
    if overlap<0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        # overlap 太大将导致 start 不前进 / 死循环
        raise ValueError("overlap must be < chunk_size")
    
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n :
        end = min(start+chunk_size,n)
        chunk = text[start:end].strip()
        # 过滤掉非常短或空的 chunk（防止垃圾块进向量库）
        if len(chunk)>=20:
            chunks.append(chunk)
        # 下一段起点：向后推进，但保留 overlap
        start = end - overlap
        # 保险：避免出现 start 不前进的情况
        if start<=0 and end == n:
            break
        if start<0:
            start = 0
        # 额外保险：如果 chunk_size 很小或 text 很短
        if end == n:
            break
    return chunks

def process_text(raw_text:str,chunk_size:int= 500,overlap:int = 100)->List[str]:
    """
    清洗 + 分块 的 pipeline（Day 7 核心能力函数）
    """
    cleaned = clean_text(raw_text)
    return chunk_text(cleaned,chunk_size=chunk_size,overlap=overlap)