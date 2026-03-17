# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path


def extract_pdf_text_and_images(binary: bytes, filename: str, max_text_pages: int = 8, max_image_pages: int = 3):
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("Missing pypdfium2, cannot parse PDF.") from exc

    doc = pdfium.PdfDocument(binary)
    texts = []
    attachments = []
    try:
        page_count = len(doc)
        for index in range(min(page_count, max_text_pages)):
            page = doc[index]
            try:
                textpage = page.get_textpage()
                page_text = textpage.get_text_range() or ""
                if page_text.strip():
                    texts.append(f"[PAGE {index + 1}]\n{page_text.strip()}")
            except Exception:
                pass

            if index < max_image_pages:
                bitmap = page.render(scale=1.6)
                image = bitmap.to_pil()
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=82, optimize=True)
                attachments.append(
                    {
                        "name": f"{Path(filename).stem}_page_{index + 1}.jpg",
                        "content": base64.b64encode(buffer.getvalue()).decode(),
                        "encoding": "base64",
                        "mimeType": "image/jpeg",
                    }
                )

        return {
            "raw_text": "\n\n".join(texts).strip(),
            "attachments": attachments,
            "page_count": page_count,
        }
    finally:
        doc.close()

