"""
src/extract/html_reader.py
==========================
Leitura de páginas HTML públicas das Bandeiras e processadores de cartões.

Fontes suportadas:
    - Cielo Developer Portal (developercielo.github.io)
    - Páginas HTML locais
    - Texto puro

Uso:
    text = fetch_html_page("https://developercielo.github.io/manual/cielo-ecommerce")
    pages = [text]  # Trata como uma única página
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def fetch_html_page(url: str, timeout: float = 30.0) -> str:
    """
    Faz download de uma página HTML e extrai o texto legível.

    Args:
        url: URL completa da página.
        timeout: Timeout em segundos.

    Returns:
        Texto extraído da página (sem tags HTML).
    """
    try:
        import httpx
        from html.parser import HTMLParser

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (research bot — interchange-ai pipeline; "
                "contact: academia@example.com)"
            )
        }

        logger.info("Baixando página: %s", url)
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()

        html = response.text
        return _html_to_text(html)

    except Exception as exc:
        logger.error("Erro ao baixar %s: %s", url, exc)
        return ""


def _html_to_text(html: str) -> str:
    """
    Converte HTML para texto simples removendo tags.

    Preserva:
        - Quebras de linha em <p>, <br>, <li>, <tr>
        - Separadores em <hr>
        - Conteúdo de tabelas (células separadas por |)
    """
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._parts: list[str] = []
            self._skip_tags = {"script", "style", "nav", "footer", "header"}
            self._current_skip = 0
            self._in_table_cell = False

        def handle_starttag(self, tag: str, attrs: list) -> None:
            if tag in self._skip_tags:
                self._current_skip += 1
            elif tag in ("p", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5"):
                self._parts.append("\n")
            elif tag in ("td", "th"):
                self._parts.append(" | ")

        def handle_endtag(self, tag: str) -> None:
            if tag in self._skip_tags:
                self._current_skip = max(0, self._current_skip - 1)

        def handle_data(self, data: str) -> None:
            if self._current_skip == 0:
                self._parts.append(data)

        def get_text(self) -> str:
            text = "".join(self._parts)
            # Colapsar linhas em branco múltiplas
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()

    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def load_local_html(path: str) -> str:
    """
    Carrega e processa um arquivo HTML local.

    Args:
        path: Caminho do arquivo .html.

    Returns:
        Texto extraído.
    """
    from pathlib import Path
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    return _html_to_text(html)


# ---------------------------------------------------------------------------
# URLs conhecidas de referência (para documentação / testes)
# ---------------------------------------------------------------------------

REFERENCE_URLS = {
    "cielo_ecommerce": "https://developercielo.github.io/manual/cielo-ecommerce",
    "cielo_checkout": "https://developercielo.github.io/manual/checkout-cielo",
    "visa_rules": "https://usa.visa.com/support/consumer/visa-rules.html",
    "mc_interchange": (
        "https://www.mastercard.com/gateway/solutions/payment-solutions/interchange.html"
    ),
}
