from __future__ import annotations

import os
import shutil
from pathlib import Path

import cv2
import fitz
import pandas as pd
import pdfplumber
import pytesseract
from pytesseract import TesseractNotFoundError

from app.core.config import get_settings

settings = get_settings()

COMMON_WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


class TesseractUnavailableError(RuntimeError):
    pass


def resolve_tesseract_cmd() -> str | None:
    env_cmd = settings.tesseract_cmd.strip() or os.getenv("TESSERACT_CMD", "").strip()
    candidates: list[str] = []

    if env_cmd:
        candidates.append(env_cmd)

    which_cmd = shutil.which("tesseract")
    if which_cmd:
        candidates.append(which_cmd)

    candidates.extend(COMMON_WINDOWS_TESSERACT_PATHS)

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    return None


def configure_tesseract() -> None:
    cmd = resolve_tesseract_cmd()
    if not cmd:
        raise TesseractUnavailableError("Tesseract executable not found. Set TESSERACT_CMD in backend/.env.")
    pytesseract.pytesseract.tesseract_cmd = cmd


def is_tesseract_available() -> bool:
    try:
        configure_tesseract()
        return True
    except Exception:
        return False


def preprocess_image(image_path: str) -> str:
    image = cv2.imread(image_path)
    if image is None:
        return ""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray)
    thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    try:
        configure_tesseract()
        return pytesseract.image_to_string(thresh, config="--oem 3 --psm 6")
    except TesseractNotFoundError as exc:
        raise TesseractUnavailableError(str(exc))
    except TesseractUnavailableError:
        raise
    except Exception:
        return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    chunks: list[str] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(text)
    except Exception:
        pass

    if chunks:
        return "\n".join(chunks)

    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text = page.get_text() or ""
            if text.strip():
                chunks.append(text)
        return "\n".join(chunks)
    except Exception:
        return ""


def extract_text_from_csv(csv_path: str) -> str:
    try:
        df = pd.read_csv(csv_path)
        return df.to_csv(index=False)
    except Exception:
        return ""


def extract_text_from_image(image_path: str) -> str:
    return preprocess_image(image_path)