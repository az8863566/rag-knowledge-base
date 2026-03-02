"""纯文本解析器：支持 .txt 和 .md 文件"""

import chardet


def parse_text(file_path: str) -> str:
    """
    解析纯文本文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件文本内容
    """
    # 检测文件编码
    with open(file_path, "rb") as f:
        raw_data = f.read()
        detected = chardet.detect(raw_data)
        encoding = detected.get("encoding", "utf-8") or "utf-8"

    # 使用检测到的编码读取文件
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except UnicodeDecodeError:
        # 如果检测的编码失败，尝试常用编码
        for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        raise ValueError(f"无法识别文件编码: {file_path}")
