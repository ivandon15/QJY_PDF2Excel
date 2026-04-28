"""
core/file_reader.py — 按文档顺序从 PDF / DOCX 提取图片
返回 list of (index, image_bytes, ext)
"""
from pathlib import Path


def extract_images(file_path: str) -> list[tuple[int, bytes, str]]:
    """
    按文档顺序提取图片。
    返回 [(0, bytes, 'png'), (1, bytes, 'jpeg'), ...]
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _from_pdf(file_path)
    elif ext == ".docx":
        return _from_docx(file_path)
    else:
        raise ValueError(f"不支持的文件格式：{ext}，请使用 PDF 或 DOCX 文件")


def _from_pdf(path: str) -> list[tuple[int, bytes, str]]:
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    results = []
    idx = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        for img in page.get_images(full=True):
            xref = img[0]
            img_data = doc.extract_image(xref)
            raw = img_data["image"]
            img_ext = img_data["ext"].lower()
            if img_ext == "jpg":
                img_ext = "jpeg"
            results.append((idx, raw, img_ext))
            idx += 1
    doc.close()
    return results


def _from_docx(path: str) -> list[tuple[int, bytes, str]]:
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(path)
    results = []
    idx = 0
    for elem in doc.element.body.iter():
        if elem.tag == qn("a:blip"):
            r_id = elem.get(qn("r:embed"))
            if r_id and r_id in doc.part.rels:
                rel = doc.part.rels[r_id]
                if "image" in rel.reltype:
                    img_bytes = rel.target_part.blob
                    ct = rel.target_part.content_type  # e.g. "image/jpeg"
                    img_ext = ct.split("/")[-1].lower()
                    if img_ext == "jpg":
                        img_ext = "jpeg"
                    results.append((idx, img_bytes, img_ext))
                    idx += 1
    return results
