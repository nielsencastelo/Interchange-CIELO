"""
src/extract/patterns.py
=======================
Expressões regulares e funções de extração de padrões numéricos e textuais
encontrados nos manuais das Bandeiras (Visa e Mastercard).

Padrões implementados:
    - Percentuais (1,17% / 0.50% / +0.35%)
    - Valores em BRL (R$ 8,00 / R$0,35)
    - Valores em USD ($0.65)
    - Bandas de parcelamento (2 - 6 / 7 a 12 / 7-21)
    - Tetos (limitado a R$ 0,35 / máximo por transação R$ 0,30)
    - Termos de canal (contactless / CNP / VbV / ECI5)
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Padrões numéricos
# ---------------------------------------------------------------------------

# Percentual: aceita vírgula ou ponto, sinal opcional, até 4 casas decimais
# Exemplos: 1,17% | 0.50% | -0.25% | +0.35%
PERCENT_RE = re.compile(
    r"(?P<value>[+-]?\d{1,3}(?:[.,]\d{1,4})?)\s*%"
)

# Valor em BRL com símbolo R$
# Exemplos: R$ 8,00 | R$0,35 | R$ 1.200,00
BRL_RE = re.compile(
    r"R\$\s*(?P<value>\d{1,3}(?:\.\d{3})*(?:,\d{1,4})?)"
)

# Valor em USD com símbolo $
# Exemplos: $0.65 | $1,50
USD_RE = re.compile(
    r"\$\s*(?P<value>\d{1,3}(?:[.,]\d{1,4})?)"
)

# Banda de parcelamento: N - M, N a M, N–M
# Exemplos: 2 - 6 | 7 a 12 | 7-21 | 2–6
BAND_RE = re.compile(
    r"(?P<start>\d{1,2})\s*[-–aA]\s*(?P<end>\d{1,2})"
)

# Teto por transação
# Exemplos: limitado a R$ 0,35 | teto de R$ 0,30 | máximo por transação R$ 0,35
CAP_RE = re.compile(
    r"(?:limitad[ao] a|teto de|máximo por transação|cap de|máx\.?)\s*R\$\s*"
    r"(?P<value>\d{1,3}(?:\.\d{3})*(?:,\d{1,4})?)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Padrões textuais / qualificadores
# ---------------------------------------------------------------------------

# Detecta termos que indicam canal não-presencial / autenticado
CNP_TERMS_RE = re.compile(
    r"(cartão\s+não[- ]?presente|cnp|e[- ]?commerce|vbv|verified\s+by\s+visa"
    r"|mastercard\s+id\s+check|eci\s*[0-9]?|autenticado)",
    re.IGNORECASE,
)

# Detecta termos de contactless
CONTACTLESS_RE = re.compile(
    r"(contactless|sem\s+contato|tap\s+to\s+pay|nfc)",
    re.IGNORECASE,
)

# Detecta termos de parcelamento
INSTALLMENT_RE = re.compile(
    r"(parcel[ao]?|installment|em\s+\d+\s+[xX]|\\bparcelas\\b)",
    re.IGNORECASE,
)

# Detecta termos de saque / ATM
ATM_RE = re.compile(
    r"(saque|atm|caixa\s+eletrônico|cash\s+advance|advance)",
    re.IGNORECASE,
)

# Detecta termos de pré-pago
PREPAID_RE = re.compile(
    r"(pré[- ]?pago|prepaid|pre[- ]?pago)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------


def parse_number(raw: str) -> float:
    """
    Converte string numérica no formato brasileiro ou americano para float.

    Exemplos:
        "1,17"   → 1.17
        "1.200,50" → 1200.50
        "0.50"   → 0.50
    """
    cleaned = raw.strip()
    # Formato brasileiro: 1.200,50 (ponto como milhar, vírgula como decimal)
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def find_percentages(text: str) -> list[float]:
    """
    Extrai todos os percentuais encontrados no texto.

    Args:
        text: Texto bruto do documento.

    Returns:
        Lista de valores float representando os percentuais.
        Ex: [1.17, 0.35, -0.25]
    """
    return [parse_number(m.group("value")) for m in PERCENT_RE.finditer(text)]


def find_brl_values(text: str) -> list[float]:
    """
    Extrai todos os valores em BRL (R$) do texto.

    Returns:
        Lista de floats. Ex: [8.0, 0.35]
    """
    return [parse_number(m.group("value")) for m in BRL_RE.finditer(text)]


def find_usd_values(text: str) -> list[float]:
    """
    Extrai todos os valores em USD ($) do texto.

    Returns:
        Lista de floats. Ex: [0.65, 1.50]
    """
    return [
        float(m.group("value").replace(",", "."))
        for m in USD_RE.finditer(text)
    ]


def find_installment_band(text: str) -> str | None:
    """
    Detecta e retorna a banda de parcelamento do texto.

    Returns:
        String no formato "start-end" ou None.
        Ex: "2-6" | "7-12" | "7-21"
    """
    match = BAND_RE.search(text)
    if not match:
        return None
    start, end = match.group("start"), match.group("end")
    # Valida faixas razoáveis para parcelamento de cartão
    if int(start) >= 2 and int(end) <= 60 and int(start) < int(end):
        return f"{start}-{end}"
    return None


def find_cap(text: str) -> float | None:
    """
    Detecta e retorna o valor de teto (cap) por transação.

    Returns:
        Float com o valor do teto ou None.
    """
    match = CAP_RE.search(text)
    if not match:
        return None
    return parse_number(match.group("value"))


def is_cnp(text: str) -> bool:
    """Retorna True se o texto menciona canal não-presencial."""
    return bool(CNP_TERMS_RE.search(text))


def is_contactless(text: str) -> bool:
    """Retorna True se o texto menciona transação contactless."""
    return bool(CONTACTLESS_RE.search(text))


def is_installment(text: str) -> bool:
    """Retorna True se o texto menciona parcelamento."""
    return bool(INSTALLMENT_RE.search(text))


def is_atm(text: str) -> bool:
    """Retorna True se o texto menciona saque/ATM."""
    return bool(ATM_RE.search(text))


def is_prepaid(text: str) -> bool:
    """Retorna True se o texto menciona pré-pago."""
    return bool(PREPAID_RE.search(text))


def normalize_text(text: str) -> str:
    """
    Normaliza espaços e caracteres especiais do texto.

    Remove:
        - Espaços múltiplos
        - Non-breaking spaces (\\xa0)
        - Quebras de linha redundantes
    """
    return " ".join(text.replace("\xa0", " ").split())
