"""文件解析器工厂模块"""

import os
from pathlib import Path

from parsers.text_parser import parse_text
from parsers.pdf_parser import parse_pdf
from parsers.docx_parser import parse_docx
from parsers.html_parser import parse_html
from parsers.csv_parser import parse_csv
from parsers.json_parser import parse_json
from parsers.excel_parser import parse_excel


class ParserError(Exception):
    """文件解析错误"""
    pass


# 扩展名到解析器的映射
PARSER_MAP = {
    ".txt": parse_text,
    ".md": parse_text,
    ".markdown": parse_text,
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".html": parse_html,
    ".htm": parse_html,
    ".csv": parse_csv,
    ".json": parse_json,
    ".xlsx": parse_excel,
}

# 支持的扩展名列表
SUPPORTED_EXTENSIONS = list(PARSER_MAP.keys())


def parse_file(file_path: str) -> str:
    """
    根据文件扩展名选择合适的解析器解析文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        解析后的文本内容
        
    Raises:
        ParserError: 解析失败时抛出
        FileNotFoundError: 文件不存在
        ValueError: 不支持的文件类型
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = path.suffix.lower()

    if ext not in PARSER_MAP:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        raise ValueError(
            f"不支持的文件类型: {ext}\n支持的格式: {supported}"
        )

    try:
        parser = PARSER_MAP[ext]
        return parser(file_path)
    except Exception as e:
        raise ParserError(f"解析文件失败 ({file_path}): {e}")


def get_supported_extensions() -> list[str]:
    """获取支持的文件扩展名列表"""
    return SUPPORTED_EXTENSIONS.copy()
