"""文本分块模块"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import config
from logger import logger


class TextSplitterError(Exception):
    """文本分割错误"""
    pass


def create_text_splitter() -> RecursiveCharacterTextSplitter:
    """创建文本分割器"""
    chunk_size = config.chunk_size
    chunk_overlap = config.chunk_overlap
    
    if chunk_size <= 0:
        raise TextSplitterError(f"chunk_size 必须为正整数，当前值: {chunk_size}")
    if chunk_overlap < 0:
        raise TextSplitterError(f"chunk_overlap 不能为负数，当前值: {chunk_overlap}")
    if chunk_overlap >= chunk_size:
        raise TextSplitterError(f"chunk_overlap ({chunk_overlap}) 必须小于 chunk_size ({chunk_size})")
    
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
        length_function=len,
    )


def split_text(text: str) -> list[str]:
    """
    将文本分割成小块
    
    Args:
        text: 待分割的文本
        
    Returns:
        分割后的文本块列表
        
    Raises:
        TextSplitterError: 分割失败时抛出
    """
    if text is None:
        raise TextSplitterError("文本不能为 None")
    
    if not isinstance(text, str):
        raise TextSplitterError(f"文本必须是字符串类型，当前类型: {type(text).__name__}")
    
    if not text.strip():
        logger.warning("文本内容为空，返回空列表")
        return []
    
    try:
        splitter = create_text_splitter()
        chunks = splitter.split_text(text)
        logger.debug(f"文本分割完成: {len(chunks)} 个块")
        return chunks
    except Exception as e:
        logger.error(f"文本分割失败: {e}")
        raise TextSplitterError(f"文本分割失败: {e}")
