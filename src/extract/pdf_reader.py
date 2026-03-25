"""
src/extract/pdf_reader.py
=========================
Leitura e extração de texto de documentos PDF das Bandeiras.

Estratégia:
    1. Tenta pdfplumber (melhor para tabelas e layout preservado)
    2. Fallback para pypdf (mais rápido, menos preciso em tabelas)
    3. Retorna lista de strings, uma por página

Uso:
    pages = extract_text_pages("manual_visa.pdf")
    for i, page_text in enumerate(pages, 1):
        print(f"Página {i}: {page_text[:200]}")
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_pages(path: str | Path) -> list[str]:
    """
    Extrai texto de todas as páginas de um PDF.

    Tenta pdfplumber primeiro (preserva layout de tabelas).
    Se falhar, usa pypdf como fallback.

    Args:
        path: Caminho para o arquivo PDF.

    Returns:
        Lista de strings, uma por página.
        Páginas sem texto retornam string vazia.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se o arquivo não for PDF válido.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    # Tenta ler como arquivo de texto primeiro (para os arquivos .txt de amostra)
    if path.suffix.lower() in (".txt", ".text"):
        logger.info("Lendo arquivo de texto: %s", path)
        return _read_text_file(path)

    logger.info("Extraindo texto de PDF: %s", path)

    # Tentativa 1: pdfplumber
    try:
        return _extract_with_pdfplumber(path)
    except Exception as exc:
        logger.warning("pdfplumber falhou (%s), tentando pypdf...", exc)

    # Tentativa 2: pypdf (fallback)
    try:
        return _extract_with_pypdf(path)
    except Exception as exc:
        logger.error("pypdf também falhou (%s). Arquivo pode ser escaneado.", exc)
        return []


def _read_text_file(path: Path) -> list[str]:
    """Lê arquivo de texto e divide em 'páginas' simuladas por bloco de linhas."""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Divide em blocos de ~50 linhas para simular páginas
    lines = text.splitlines()
    pages = []
    chunk_size = 50
    for i in range(0, len(lines), chunk_size):
        chunk = "\n".join(lines[i : i + chunk_size])
        if chunk.strip():
            pages.append(chunk)
    return pages if pages else [text]


def _extract_with_pdfplumber(path: Path) -> list[str]:
    """
    Extrai texto usando pdfplumber.

    Preserva melhor o layout de tabelas e colunas.
    Para tabelas, extrai cells e reconstrói como texto tabular.
    """
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        logger.info("PDF aberto com pdfplumber: %d páginas", len(pdf.pages))
        for page in pdf.pages:
            parts: list[str] = []

            # Texto corrido
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)

            # Tabelas (pdfplumber detecta automaticamente)
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if row:
                        row_text = " | ".join(
                            str(cell).strip() if cell else "" for cell in row
                        )
                        if row_text.strip():
                            parts.append(row_text)

            pages.append("\n".join(parts))

    return pages


def _extract_with_pypdf(path: Path) -> list[str]:
    """
    Extrai texto usando pypdf (fallback).

    Mais simples e robusto, mas perde posicionamento de tabelas.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    logger.info("PDF aberto com pypdf: %d páginas", len(reader.pages))

    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    return pages


def get_pdf_info(path: str | Path) -> dict[str, int | str]:
    """
    Retorna metadados básicos do PDF.

    Returns:
        Dict com 'pages', 'title', 'author', 'creator'
    """
    path = Path(path)
    info: dict[str, int | str] = {}

    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            info["pages"] = len(pdf.pages)
            meta = pdf.metadata or {}
            info["title"] = str(meta.get("Title", ""))
            info["author"] = str(meta.get("Author", ""))
            info["creator"] = str(meta.get("Creator", ""))
    except Exception:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            info["pages"] = len(reader.pages)
            meta = reader.metadata or {}
            info["title"] = str(getattr(meta, "title", ""))
        except Exception:
            info["pages"] = 0

    return info
