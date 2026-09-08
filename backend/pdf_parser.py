import pymupdf
import io

def extract_text_from_pdf(file_bytes: bytes, filename: str) -> list:
    """Extracts text from PDF bytes and returns a list of dictionaries containing text and page number."""
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    pages_text = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        # Basic cleaning
        text = " ".join(text.split())
        if len(text) > 50: # Ignore very short/empty pages
            pages_text.append({
                "page_number": page_num + 1,
                "text": text,
                "source_document": filename
            })
    
    return pages_text
