"""PDF 解析器"""

import pdfplumber


def parse_pdf(file_path: str) -> str:
    """
    解析 PDF 文件
    
    Args:
        file_path: PDF 文件路径
        
    Returns:
        提取的文本内容
    """
    texts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
    return "\n\n".join(texts)
