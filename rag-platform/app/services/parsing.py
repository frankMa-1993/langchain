from __future__ import annotations

import re
from pathlib import Path

from charset_normalizer import from_path
from docx import Document as DocxDocument
from pypdf import PdfReader


class ParseError(Exception):
    pass


def read_text_file(path: Path) -> str:
    try:
        raw = path.read_bytes()
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        best = from_path(path).best()
        if best is not None:
            return str(best)
        return raw.decode("utf-8", errors="replace")
    except OSError as e:
        raise ParseError(str(e)) from e


def parse_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
        return "\n\n".join(parts).strip()
    except Exception as e:
        raise ParseError(f"PDF parse failed: {e}") from e


def parse_docx(path: Path) -> str:
    try:
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text).strip()
    except Exception as e:
        raise ParseError(f"DOCX parse failed: {e}") from e


def parse_markdown(path: Path) -> str:
    text = read_text_file(path)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def parse_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in (".docx", ".doc"):
        if suffix == ".doc":
            raise ParseError("Legacy .doc is not supported; convert to .docx")
        return parse_docx(path)
    if suffix in (".md", ".markdown"):
        return parse_markdown(path)
    if suffix in (".txt", ".text"):
        return read_text_file(path)
    raise ParseError(f"Unsupported extension: {suffix}")
