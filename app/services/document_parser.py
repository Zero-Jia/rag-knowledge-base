from pypdf import PdfReader

def parse_txt(file_path:str)-> str:
    with open(file_path,"r",encoding="utf-8",errors="ignore") as f:
        return f.read()
    
def parse_pdf(file_path:str)->str:
    reader = PdfReader(file_path)
    text = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text.append(page_text)

    return "\n".join(text)

def parse_document(file_path:str,content_type:str)->str:
    if content_type == "text/plain":
        return parse_txt(file_path)
    if content_type == "application/pdf":
        return parse_pdf(file_path)
    raise ValueError(f"Unsupported content type: {content_type}")