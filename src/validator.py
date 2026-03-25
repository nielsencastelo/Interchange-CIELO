"""
src/validator.py
================
Validação de regras extraídas e atribuição de score de confiança.

O score de confiança (0.0 – 1.0) indica a qualidade da extração:
    >= 0.80 → Alta confiança, pronto para produção
    0.50 – 0.79 → Média confiança, revisar antes de usar
    < 0.50 → Baixa confiança, requer revisão humana obrigatória

Critérios de pontuação:
    Positivos:
        + Contém palavra-chave de contexto (contactless, parcel, etc.)
        + Produto identificado
        + Segmento de comércio identificado
        + Canal identificado
        + Público identificado
        + Banda de parcelamento identificada
        + Taxa dentro de faixas esperadas para Visa/MC BR

    Negativos:
        - Taxa fora de faixas esperadas
        - Taxa fixa negativa
        - Evidence text muito curto
"""
from __future__ import annotations

import logging

from .schemas import RuleCandidate

logger = logging.getLogger(__name__)

# Faixas esperadas para taxas de intercâmbio no Brasil (baseado em dados públicos)
# Fonte: Banco Central do Brasil + manuais públicos Visa/Mastercard
RATE_RANGES = {
    "credit": (0.30, 3.50),      # Crédito: 0,30% a 3,50%
    "debit": (0.10, 1.20),       # Débito: 0,10% a 1,20%
    "prepaid": (0.10, 1.50),     # Pré-pago: 0,10% a 1,50%
    "cash_withdrawal": (0.0, 0.0),  # Saque: taxa fixa, percentual = 0
}

# Faixas de ajustes (negativos ou positivos)
ADJUSTMENT_RANGE = (-3.0, 3.0)

# Faixas de taxa fixa em BRL para saque
FIXED_FEE_RANGE_BRL = (0.50, 30.0)


def validate_rule(rule: RuleCandidate) -> RuleCandidate:
    """
    Valida uma RuleCandidate e ajusta seu score de confiança.

    A validação não rejeita regras — apenas ajusta o score para
    indicar ao downstream a qualidade da extração.

    Args:
        rule: Regra candidata a validar.

    Returns:
        Nova instância da regra com score ajustado.
    """
    score = rule.confidence_score
    evidence = rule.evidence_text.lower()

    # -----------------------------------------------------------------------
    # Penalidades (reduzem o score)
    # -----------------------------------------------------------------------

    # Taxa percentual fora de faixas esperadas
    if rule.rate_pct is not None:
        if rule.rule_type == "base_rate":
            family = rule.card_family or "credit"
            min_r, max_r = RATE_RANGES.get(family, (-5.0, 10.0))
            if not (min_r <= rule.rate_pct <= max_r):
                score = min(score, 0.25)
                logger.debug(
                    "Taxa %.2f fora da faixa esperada para %s [%.2f, %.2f]",
                    rule.rate_pct, family, min_r, max_r,
                )
        elif "adjustment" in rule.rule_type:
            if not (ADJUSTMENT_RANGE[0] <= rule.rate_pct <= ADJUSTMENT_RANGE[1]):
                score = min(score, 0.30)

    # Taxa fixa negativa é impossível
    if rule.fixed_fee_amount is not None and rule.fixed_fee_amount < 0:
        score = min(score, 0.15)

    # Taxa fixa fora da faixa BRL
    if rule.fixed_fee_amount is not None and rule.rule_type == "fixed_fee":
        if not (FIXED_FEE_RANGE_BRL[0] <= rule.fixed_fee_amount <= FIXED_FEE_RANGE_BRL[1]):
            score = min(score, 0.35)

    # Evidence text muito curto → extração pode ser imprecisa
    if len(rule.evidence_text.strip()) < 15:
        score = min(score, 0.30)

    # -----------------------------------------------------------------------
    # Bônus (aumentam o score)
    # -----------------------------------------------------------------------

    # Palavras-chave de contexto relevantes
    context_keywords = [
        "contactless", "parcel", "cnp", "pré-pago", "pre-pago",
        "saque", "vbv", "eci", "mastercard", "visa", "intercâmbio",
        "interchange", "taxa", "percentual", "débito", "crédito",
    ]
    if any(k in evidence for k in context_keywords):
        score = min(1.0, score + 0.08)

    # Produto identificado
    if rule.product:
        score = min(1.0, score + 0.06)

    # Segmento de comércio identificado
    if rule.merchant_group:
        score = min(1.0, score + 0.06)

    # Canal identificado
    if rule.channel:
        score = min(1.0, score + 0.05)

    # Público identificado
    if rule.audience:
        score = min(1.0, score + 0.05)

    # Banda de parcelamento identificada (relevante para installment_adjustment)
    if rule.installment_band and rule.rule_type == "installment_adjustment":
        score = min(1.0, score + 0.08)

    # Cap identificado junto com regra de cap
    if rule.cap_amount and rule.rule_type == "cap":
        score = min(1.0, score + 0.10)

    final_score = round(score, 2)

    if final_score < 0.50:
        logger.debug(
            "Regra com baixo score (%.2f): %s / %s / %s",
            final_score, rule.network, rule.rule_type, rule.product,
        )

    return rule.model_copy(update={"confidence_score": final_score})


def filter_by_confidence(
    rules: list[RuleCandidate],
    min_score: float = 0.50,
) -> list[RuleCandidate]:
    """
    Filtra regras pelo score mínimo de confiança.

    Args:
        rules:     Lista de regras a filtrar.
        min_score: Score mínimo (default: 0.50).

    Returns:
        Subconjunto das regras com score >= min_score.
    """
    return [r for r in rules if r.confidence_score >= min_score]


def get_confidence_label(score: float) -> str:
    """
    Retorna rótulo textual para o score de confiança.

    Returns:
        "alta" | "média" | "baixa"
    """
    if score >= 0.80:
        return "alta"
    if score >= 0.50:
        return "média"
    return "baixa"
