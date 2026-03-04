"""HTML 解析器"""

from bs4 import BeautifulSoup

from parsers.text_parser import parse_text


def parse_html(file_path: str) -> str:
    """
    解析 HTML 文件
    
    Args:
        file_path: HTML 文件路径
        
    Returns:
        提取的文本内容
    """
    raw_html = parse_text(file_path)
    soup = BeautifulSoup(raw_html, "lxml")

    # 移除脚本和样式标签
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # 提取文本
    text = soup.get_text(separator="\n", strip=True)

    # 清理多余空行
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n\n".join(lines)
