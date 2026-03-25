"""
src/normalizer.py
=================
Inferência de campos e normalização de regras extraídas dos manuais.

A normalização usa heurísticas de NLP simples (busca de termos-chave)
para preencher campos quando o texto não os explicita diretamente.

Funções públicas:
    normalize_snippet(text, network, region, page_number) → list[RuleCandidate]
    infer_rule_type(text)       → str
    infer_channel(text)         → str | None
    infer_card_family(text)     → str | None
    infer_product(text)         → str | None
    infer_audience(text)        → str | None
    infer_merchant_group(text)  → str | None
"""
from __future__ import annotations

import logging

from .extract.patterns import (
    find_brl_values,
    find_cap,
    find_installment_band,
    find_percentages,
    is_atm,
    is_cnp,
    is_contactless,
    is_installment,
    is_prepaid,
    normalize_text,
)
from .schemas import RuleCandidate
from .validator import validate_rule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inferência de tipo de regra
# ---------------------------------------------------------------------------

def infer_rule_type(text: str) -> str:
    """
    Infere o tipo de regra baseado em palavras-chave no texto.

    Precedência (da mais específica para a mais geral):
        1. Contactless
        2. CNP (autenticado ou não)
        3. Parcelado
        4. Saque/ATM
        5. Teto (cap)
        6. Captura
        7. Produto especial
        8. Ajuste por segmento
        9. Taxa base (default)
    """
    lowered = text.lower()

    if is_contactless(text):
        return "contactless_adjustment"

    if "eci5" in lowered or "eci 5" in lowered or "vbv" in lowered or "autenticado" in lowered:
        return "cnp_authenticated_adjustment"

    if is_cnp(text):
        return "cnp_adjustment"

    if is_installment(text):
        return "installment_adjustment"

    if is_atm(text):
        return "fixed_fee"

    if "teto" in lowered or "limitado a" in lowered or "limitada a" in lowered or "máximo por transação" in lowered:
        return "cap"

    if "modalidade de captura" in lowered or "ajuste de captura" in lowered:
        return "capture_adjustment"

    if "on digital" in lowered or "produto especial" in lowered or "digital first" in lowered:
        return "special_product_adjustment"

    if any(
        seg in lowered
        for seg in [
            "supermercado", "posto", "farmácia", "hotel", "segmento",
            "merchant", "comércio", "mcc", "grupo de estabelecimento",
        ]
    ):
        return "merchant_adjustment"

    return "base_rate"


# ---------------------------------------------------------------------------
# Inferência de canal
# ---------------------------------------------------------------------------

def infer_channel(text: str) -> str | None:
    """Infere o canal da transação a partir do texto."""
    if is_atm(text):
        return "atm"
    if is_contactless(text):
        return "cp_contactless"
    if is_cnp(text):
        return "cnp"
    lowered = text.lower()
    if "cartão presente" in lowered or " cp " in f" {lowered} ":
        return "cp"
    return None


# ---------------------------------------------------------------------------
# Inferência de família de cartão
# ---------------------------------------------------------------------------

def infer_card_family(text: str) -> str | None:
    """Infere a família (credit, debit, prepaid, cash_withdrawal) do texto."""
    if is_atm(text):
        return "cash_withdrawal"
    if is_prepaid(text):
        return "prepaid"
    lowered = text.lower()
    if "débito" in lowered or "debit" in lowered:
        return "debit"
    if "crédito" in lowered or "credit" in lowered:
        return "credit"
    return None


# ---------------------------------------------------------------------------
# Inferência de produto
# ---------------------------------------------------------------------------

# Mapeamento de termos → nome canônico do produto
_PRODUCT_MAP: list[tuple[str, str]] = [
    # Visa
    ("infinite", "Infinite"),
    ("signature", "Signature"),
    ("platinum", "Platinum"),
    ("gold", "Gold"),
    ("classic", "Classic"),
    # Mastercard
    ("world legend", "World_Legend"),
    ("world elite", "World_Elite"),
    ("black", "Black"),
    # Comerciais Mastercard
    ("commercial affluent", "Commercial_Affluent"),
    ("commercial business", "Commercial_Business"),
    ("commercial cta", "Commercial_CTA"),
    ("p-card", "Commercial_PCard"),
    ("pcard", "Commercial_PCard"),
    ("agro", "Commercial_Agro"),
    # Visa PJ
    ("corporativo", "Corporativo"),
    ("compras empresarial", "Compras_Empresarial_Platinum"),
    ("empresarial", "Empresarial"),
    # Pré-pago
    ("consumer prepaid", "Consumer_Prepaid"),
    ("prepago pf", "PrePago_PF"),
    ("prepago pj", "PrePago_PJ"),
    # ATM
    ("atm tier ii", "ATM_Tier_II"),
    ("atm tier i", "ATM_Tier_I"),
    ("atm tier", "ATM_Tier_I"),
]


def infer_product(text: str) -> str | None:
    """Infere o produto específico do cartão a partir do texto."""
    lowered = text.lower()
    for term, canonical in _PRODUCT_MAP:
        if term in lowered:
            return canonical
    return None


# ---------------------------------------------------------------------------
# Inferência de público (audience)
# ---------------------------------------------------------------------------

def infer_audience(text: str) -> str | None:
    """Infere o público-alvo (PF / PJ / ALL) a partir do texto."""
    lowered = text.lower()
    if (
        "pessoa física" in lowered
        or "consumidor" in lowered
        or " pf " in f" {lowered} "
        or "portador" in lowered
    ):
        return "PF"
    if (
        "pessoa jurídica" in lowered
        or "comercial" in lowered
        or "corporativo" in lowered
        or " pj " in f" {lowered} "
        or "empresarial" in lowered
    ):
        return "PJ"
    return None


# ---------------------------------------------------------------------------
# Inferência de segmento de comércio
# ---------------------------------------------------------------------------

_MERCHANT_MAP: list[tuple[str, str]] = [
    ("supermercado", "supermercados"),
    ("atacadista", "atacadistas"),
    ("posto", "postos_farmacias_departamento_aereas"),
    ("farmácia", "postos_farmacias_departamento_aereas"),
    ("drogaria", "postos_farmacias_departamento_aereas"),
    ("loja de departamento", "postos_farmacias_departamento_aereas"),
    ("cia aérea", "postos_farmacias_departamento_aereas"),
    ("companhia aérea", "postos_farmacias_departamento_aereas"),
    ("hotel", "hoteis_aluguel_carros_turismo_joalherias_telemarketing"),
    ("aluguel de carro", "hoteis_aluguel_carros_turismo_joalherias_telemarketing"),
    ("joalheria", "hoteis_aluguel_carros_turismo_joalherias_telemarketing"),
    ("telemarketing", "hoteis_aluguel_carros_turismo_joalherias_telemarketing"),
    ("turismo", "hoteis_aluguel_carros_turismo_joalherias_telemarketing"),
    ("transporte público", "transporte_publico"),
    ("micro comércio", "micro_comercios"),
    ("loteria", "loteria"),
    ("serviço governamental", "servicos_governamentais"),
    ("governo", "servicos_governamentais"),
    ("despesa geral", "despesas_gerais"),
    ("outros", "outros"),
]


def infer_merchant_group(text: str) -> str | None:
    """Infere o segmento de comércio (merchant group) a partir do texto."""
    lowered = text.lower()
    for term, canonical in _MERCHANT_MAP:
        if term in lowered:
            return canonical
    return None


# ---------------------------------------------------------------------------
# Normalizador principal de snippets
# ---------------------------------------------------------------------------

def normalize_snippet(
    text: str,
    network: str,
    region: str = "BR",
    page_number: int | None = None,
) -> list[RuleCandidate]:
    """
    Extrai e normaliza regras de um trecho de texto dos manuais das Bandeiras.

    Algoritmo:
        1. Normaliza o texto (espaços, unicode)
        2. Extrai percentuais, valores BRL, bandas e caps via regex
        3. Infere campos contextuais (produto, canal, segmento, etc.)
        4. Cria RuleCandidate para cada valor encontrado
        5. Valida e atribui score de confiança

    Args:
        text:        Trecho de texto do documento.
        network:     Bandeira ("Visa" | "Mastercard").
        region:      Região (default "BR").
        page_number: Número da página de origem.

    Returns:
        Lista de RuleCandidate normalizados e validados.
    """
    clean = normalize_text(text)
    if not clean:
        return []

    percentages = find_percentages(clean)
    brl_values = find_brl_values(clean)
    band = find_installment_band(clean)
    cap = find_cap(clean)

    rules: list[RuleCandidate] = []

    # Cria uma regra para cada percentual encontrado
    for pct in percentages:
        rule = RuleCandidate(
            network=network,
            region=region,
            audience=infer_audience(clean),
            card_family=infer_card_family(clean),
            product=infer_product(clean),
            merchant_group=infer_merchant_group(clean),
            channel=infer_channel(clean),
            installment_band=band,
            rule_type=infer_rule_type(clean),
            rate_pct=pct,
            cap_amount=cap,
            evidence_text=clean[:500],  # Limita tamanho do evidence text
            page_number=page_number,
            confidence_score=0.55,
        )
        rules.append(validate_rule(rule))

    # Cria regras de taxa fixa (saque ATM)
    if brl_values and is_atm(clean):
        for value in brl_values:
            rule = RuleCandidate(
                network=network,
                region=region,
                audience=infer_audience(clean),
                card_family="cash_withdrawal",
                product=infer_product(clean),
                merchant_group=None,
                channel="atm",
                installment_band=None,
                rule_type="fixed_fee",
                fixed_fee_amount=value,
                currency="BRL",
                cap_amount=cap,
                evidence_text=clean[:500],
                page_number=page_number,
                confidence_score=0.60,
            )
            rules.append(validate_rule(rule))

    logger.debug(
        "normalize_snippet: %d percentuais, %d brl, %d regras extraídas",
        len(percentages), len(brl_values), len(rules),
    )

    return rules
