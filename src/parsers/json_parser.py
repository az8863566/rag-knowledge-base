"""JSON 解析器"""

import json

from parsers.text_parser import parse_text


def _flatten_json(obj, prefix: str = "") -> list[str]:
    """递归扁平化 JSON 对象"""
    lines = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            lines.extend(_flatten_json(value, new_prefix))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_prefix = f"{prefix}[{i}]"
            lines.extend(_flatten_json(item, new_prefix))
    else:
        # 基本类型
        value_str = str(obj) if obj is not None else "null"
        lines.append(f"{prefix}: {value_str}")

    return lines


def parse_json(file_path: str) -> str:
    """
    解析 JSON 文件
    
    Args:
        file_path: JSON 文件路径
        
    Returns:
        扁平化后的文本内容
    """
    raw_content = parse_text(file_path)
    data = json.loads(raw_content)

    lines = _flatten_json(data)
    return "\n".join(lines)
