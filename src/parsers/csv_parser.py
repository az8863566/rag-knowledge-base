"""CSV 解析器"""

import csv

from parsers.text_parser import parse_text


def parse_csv(file_path: str) -> str:
    """
    解析 CSV 文件
    
    Args:
        file_path: CSV 文件路径
        
    Returns:
        表格文本内容
    """
    raw_content = parse_text(file_path)
    lines = raw_content.strip().split("\n")
    
    if not lines:
        return ""

    # 使用 csv 模块解析
    reader = csv.reader(lines)
    rows = list(reader)

    if not rows:
        return ""

    # 格式化为文本表格
    texts = []
    header = rows[0] if rows else []
    
    if header:
        texts.append("表头: " + " | ".join(header))
        texts.append("-" * 40)

    for i, row in enumerate(rows[1:], 1):
        # 将每行数据与表头配对
        if header:
            row_text = " | ".join(
                f"{h}: {v}" for h, v in zip(header, row) if v.strip()
            )
        else:
            row_text = " | ".join(row)
        if row_text:
            texts.append(f"行 {i}: {row_text}")

    return "\n".join(texts)
