# -*- coding: utf-8 -*-
"""PDF / 图片 文本提取服务

策略（按可用性自动降级）：
  1. PDF：用 pdfplumber 提取每页文本
     - 如果文本量充足（每页平均 > MIN_CHARS_PER_PAGE 字符），直接用
     - 否则视为扫描件，走 OCR 兜底（如果 OCR 可用）
  2. 图片：直接走 OCR

OCR 后端按可用性优先级：
  - PaddleOCR（中文好，需要 GPU 时性能更佳）
  - pytesseract（轻量，需要 tesseract 二进制）
  - 都不可用：标记 needs_ocr=True，由人工处理

依赖（manifest 里都标为 external_dependencies，缺一不可的只有 pdfplumber）：
  pip install pdfplumber pillow
  pip install paddlepaddle paddleocr   (可选)
  pip install pytesseract              (可选, 还需系统装 tesseract)
"""

import io
import logging
import re
from typing import Optional

_logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 30


class PdfExtractError(Exception):
    pass


def is_pdfplumber_available() -> bool:
    try:
        import pdfplumber  # noqa: F401
        return True
    except ImportError:
        return False


def is_paddleocr_available() -> bool:
    try:
        from paddleocr import PaddleOCR  # noqa: F401
        return True
    except ImportError:
        return False


def is_pytesseract_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_pdf_text(file_bytes: bytes, ocr_lang: str = "ch") -> dict:
    """从 PDF 字节流提取文本。

    返回：
      {
        "ok": bool,
        "text": str,              # 提取出的纯文本
        "markdown": str,          # 加了页码标记的 markdown
        "page_count": int,
        "method": "pdfplumber" | "ocr_paddle" | "ocr_tesseract" | "skipped",
        "needs_ocr": bool,        # 文本不够，但 OCR 不可用 → 需要人工
        "error": str | None,
      }
    """
    if not is_pdfplumber_available():
        return _err("缺少依赖 pdfplumber，请安装：pip install pdfplumber")

    import pdfplumber  # type: ignore

    pages_text: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = (page.extract_text(x_tolerance=2, y_tolerance=2) or "").strip()
                pages_text.append(page_text)
    except Exception as exc:
        return _err(f"pdfplumber 解析失败：{exc}")

    total_chars = sum(len(text) for text in pages_text)
    avg_per_page = total_chars / max(page_count, 1)
    text_layer_ok = avg_per_page >= MIN_CHARS_PER_PAGE

    if text_layer_ok:
        cleaned_pages = [_normalize_text(text) for text in pages_text]
        markdown = _to_markdown(cleaned_pages)
        return {
            "ok": True,
            "text": "\n\n".join(filter(None, cleaned_pages)),
            "markdown": markdown,
            "page_count": page_count,
            "method": "pdfplumber",
            "needs_ocr": False,
            "error": None,
        }

    ocr_method = None
    ocr_pages: list[str] = []
    if is_paddleocr_available():
        try:
            ocr_pages = _ocr_pdf_with_paddle(file_bytes, lang=ocr_lang)
            ocr_method = "ocr_paddle"
        except Exception as exc:
            _logger.warning("PaddleOCR 失败：%s，回退 tesseract", exc)

    if not ocr_pages and is_pytesseract_available():
        try:
            ocr_pages = _ocr_pdf_with_tesseract(file_bytes, lang=_tesseract_lang(ocr_lang))
            ocr_method = "ocr_tesseract"
        except Exception as exc:
            _logger.warning("Tesseract 失败：%s", exc)

    if not ocr_pages:
        partial = "\n\n".join(filter(None, [_normalize_text(t) for t in pages_text]))
        return {
            "ok": False,
            "text": partial,
            "markdown": _to_markdown([_normalize_text(t) for t in pages_text]),
            "page_count": page_count,
            "method": "skipped",
            "needs_ocr": True,
            "error": "扫描件且 OCR 不可用，请安装 paddleocr 或 pytesseract，或手工处理",
        }

    cleaned_pages = [_normalize_text(t) for t in ocr_pages]
    return {
        "ok": True,
        "text": "\n\n".join(filter(None, cleaned_pages)),
        "markdown": _to_markdown(cleaned_pages),
        "page_count": page_count,
        "method": ocr_method,
        "needs_ocr": False,
        "error": None,
    }


def extract_image_text(file_bytes: bytes, ocr_lang: str = "ch") -> dict:
    """对单张图片做 OCR。"""
    if is_paddleocr_available():
        try:
            text = _ocr_image_with_paddle(file_bytes, lang=ocr_lang)
            return _ok_image(text, "ocr_paddle")
        except Exception as exc:
            _logger.warning("PaddleOCR 图片失败：%s", exc)
    if is_pytesseract_available():
        try:
            text = _ocr_image_with_tesseract(file_bytes, lang=_tesseract_lang(ocr_lang))
            return _ok_image(text, "ocr_tesseract")
        except Exception as exc:
            _logger.warning("Tesseract 图片失败：%s", exc)
    return _err("图片 OCR 不可用，请安装 paddleocr 或 pytesseract", needs_ocr=True)


# ---------------------------------------------------------------------------
# OCR backends
# ---------------------------------------------------------------------------

_paddle_ocr_singleton = None


def _get_paddle_ocr(lang: str):
    global _paddle_ocr_singleton
    if _paddle_ocr_singleton is None:
        from paddleocr import PaddleOCR  # type: ignore
        _paddle_ocr_singleton = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    return _paddle_ocr_singleton


def _ocr_pdf_with_paddle(file_bytes: bytes, lang: str) -> list[str]:
    images = _pdf_to_images(file_bytes)
    ocr = _get_paddle_ocr(lang)
    pages = []
    for image_bytes in images:
        pages.append(_paddle_run(ocr, image_bytes))
    return pages


def _ocr_image_with_paddle(file_bytes: bytes, lang: str) -> str:
    ocr = _get_paddle_ocr(lang)
    return _paddle_run(ocr, file_bytes)


def _paddle_run(ocr, image_bytes: bytes) -> str:
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore

    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    array = np.array(image)
    result = ocr.ocr(array, cls=True)
    lines = []
    for block in result or []:
        for entry in block or []:
            if not entry:
                continue
            text = (entry[1][0] if isinstance(entry[1], (list, tuple)) else entry[1]) or ""
            text = str(text).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _ocr_pdf_with_tesseract(file_bytes: bytes, lang: str) -> list[str]:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore

    images = _pdf_to_images(file_bytes)
    pages = []
    for image_bytes in images:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang=lang)
        pages.append((text or "").strip())
    return pages


def _ocr_image_with_tesseract(file_bytes: bytes, lang: str) -> str:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore

    image = Image.open(io.BytesIO(file_bytes))
    return (pytesseract.image_to_string(image, lang=lang) or "").strip()


def _pdf_to_images(file_bytes: bytes) -> list[bytes]:
    """优先使用 pdf2image（依赖 poppler），不可用则用 pdfplumber 自带渲染。"""
    try:
        from pdf2image import convert_from_bytes  # type: ignore
    except ImportError:
        return _pdf_to_images_via_pdfplumber(file_bytes)
    images = convert_from_bytes(file_bytes, dpi=200)
    out = []
    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        out.append(buffer.getvalue())
    return out


def _pdf_to_images_via_pdfplumber(file_bytes: bytes) -> list[bytes]:
    import pdfplumber  # type: ignore

    out = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            buffer = io.BytesIO()
            image = page.to_image(resolution=150)
            image.save(buffer, format="PNG")
            out.append(buffer.getvalue())
    return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_LIGATURE_FIXES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "­": "",
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    for src, dst in _LIGATURE_FIXES.items():
        text = text.replace(src, dst)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _to_markdown(pages: list[str]) -> str:
    parts = []
    for idx, page in enumerate(pages, start=1):
        if not page:
            continue
        parts.append(f"## 第 {idx} 页\n\n{page}")
    return "\n\n".join(parts)


def _tesseract_lang(lang: str) -> str:
    mapping = {
        "ch": "chi_sim",
        "chinese": "chi_sim",
        "zh": "chi_sim",
        "en": "eng",
        "english": "eng",
    }
    return mapping.get((lang or "").lower(), lang or "eng")


def _err(message: str, needs_ocr: bool = False) -> dict:
    return {
        "ok": False,
        "text": "",
        "markdown": "",
        "page_count": 0,
        "method": "skipped",
        "needs_ocr": needs_ocr,
        "error": message,
    }


def _ok_image(text: str, method: str) -> dict:
    cleaned = _normalize_text(text)
    return {
        "ok": True,
        "text": cleaned,
        "markdown": cleaned,
        "page_count": 1,
        "method": method,
        "needs_ocr": False,
        "error": None,
    }
