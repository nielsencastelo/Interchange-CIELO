"""
src/simulator.py
================
Motor de simulação de taxas de intercâmbio.

Permite calcular a taxa efetiva para uma transação dado:
    - Bandeira, família de cartão, produto
    - Segmento de comércio, canal, parcelamento
    - Valor da transação (para cálculo do fee absoluto)

Algoritmo de simulação:
    1. Filtra regras que correspondem aos parâmetros
    2. Aplica taxa BASE do produto
    3. Soma ajustes (segmento, parcelamento, canal, contactless)
    4. Aplica cap/floor se existir
    5. Retorna taxa final + valor absoluto estimado

Uso:
    from src.simulator import simulate, SimulationResult
    result = simulate(rules, request)
    print(f"Taxa efetiva: {result.total_rate_pct:.2f}%")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .schemas import RuleCandidate, SimulationRequest, SimulationResponse

logger = logging.getLogger(__name__)

# Tipos de regra que representam taxa base (apenas um deve ser aplicado)
BASE_RATE_TYPES = {"base_rate"}

# Tipos de regra que representam ajustes (podem ser somados)
ADJUSTMENT_TYPES = {
    "merchant_adjustment",
    "installment_adjustment",
    "contactless_adjustment",
    "cnp_adjustment",
    "cnp_authenticated_adjustment",
    "capture_adjustment",
    "special_product_adjustment",
}

# Tipos que representam taxas fixas (não percentuais)
FIXED_FEE_TYPES = {"fixed_fee"}

# Tipos de cap/floor (limitam o resultado)
LIMIT_TYPES = {"cap", "floor", "regulatory_cap"}


def _matches(rule_value: str | None, request_value: str | None) -> bool:
    """
    Verifica se o campo de uma regra corresponde ao valor do request.

    Regras:
        - None no campo da regra → aceita qualquer valor (wildcard)
        - "all" no campo da regra → aceita qualquer valor
        - None no request → aceita qualquer regra
        - Igualdade exata → match

    Args:
        rule_value:    Valor do campo na regra (pode ser None/"all").
        request_value: Valor do campo no request de simulação.

    Returns:
        True se há correspondência.
    """
    if rule_value is None or rule_value.lower() == "all":
        return True
    if request_value is None:
        return True
    return rule_value.lower() == request_value.lower()


def _installment_band_matches(
    rule_band: str | None, request_band: str | None
) -> bool:
    """
    Verifica correspondência de banda de parcelamento.

    Lógica especial: "avista" (à vista) é tratado como sem parcelamento.
    Uma regra para "2-6" não se aplica a transações à vista.

    Args:
        rule_band:    Banda da regra ("2-6", "7-12", "avista", None).
        request_band: Banda do request.

    Returns:
        True se corresponde.
    """
    if rule_band is None or rule_band.lower() == "all":
        return True

    if request_band is None or request_band.lower() == "avista":
        # Transação à vista: só aceita regras "avista" ou sem banda
        return rule_band.lower() in ("avista", "all")

    # Ambas têm bandas: verifica se o request cabe na faixa da regra
    try:
        req_installments_str = request_band.split("-")
        if len(req_installments_str) == 1:
            req_n = int(req_installments_str[0])
        else:
            req_n = int(req_installments_str[0])  # Usa o início da faixa do request

        rule_parts = rule_band.split("-")
        if len(rule_parts) == 2:
            rule_start, rule_end = int(rule_parts[0]), int(rule_parts[1])
            return rule_start <= req_n <= rule_end
    except (ValueError, IndexError):
        pass

    return rule_band == request_band


def filter_applicable_rules(
    rules: list[RuleCandidate],
    request: SimulationRequest,
) -> list[RuleCandidate]:
    """
    Filtra regras aplicáveis para uma determinada transação.

    Args:
        rules:   Lista completa de regras disponíveis.
        request: Parâmetros da transação a simular.

    Returns:
        Subconjunto de regras que se aplicam.
    """
    applicable: list[RuleCandidate] = []

    for rule in rules:
        # Filtros obrigatórios
        if rule.network.lower() != request.network.lower():
            continue
        if rule.region.lower() != request.region.lower():
            continue

        # Filtros de segmentação (com wildcard)
        if not _matches(rule.audience, request.audience):
            continue
        if not _matches(rule.card_family, request.card_family):
            continue
        if not _matches(rule.product, request.product):
            continue
        if not _matches(rule.merchant_group, request.merchant_group):
            continue
        if not _matches(rule.channel, request.channel):
            continue
        if not _installment_band_matches(rule.installment_band, request.installment_band):
            continue

        applicable.append(rule)

    return applicable


def simulate(
    rules: list[RuleCandidate],
    request: SimulationRequest,
) -> SimulationResponse:
    """
    Calcula a taxa efetiva de intercâmbio para uma transação.

    Algoritmo em camadas:
        1. BASE_RATE: aplica apenas a taxa base do produto (a mais específica)
        2. ADJUSTMENTS: soma todos os ajustes aplicáveis
        3. FIXED_FEE: soma taxas fixas (ATM, etc.)
        4. LIMITS: aplica cap/floor ao resultado

    Args:
        rules:   Lista de regras disponíveis (tipicamente do banco de dados).
        request: Parâmetros da transação a simular.

    Returns:
        SimulationResponse com taxa total, regras aplicadas e notas.
    """
    applicable = filter_applicable_rules(rules, request)
    notes: list[str] = []

    if not applicable:
        notes.append(
            "Nenhuma regra encontrada para os parâmetros informados. "
            "Verifique se a base de dados foi carregada (python -m src.seed_sample_data)."
        )
        return SimulationResponse(
            matched_rules=[],
            total_rate_pct=0.0,
            total_fixed_fee=0.0,
            notes=notes,
        )

    # Separar regras por tipo
    base_rules = [r for r in applicable if r.rule_type in BASE_RATE_TYPES]
    adj_rules = [r for r in applicable if r.rule_type in ADJUSTMENT_TYPES]
    fixed_rules = [r for r in applicable if r.rule_type in FIXED_FEE_TYPES]
    limit_rules = [r for r in applicable if r.rule_type in LIMIT_TYPES]

    # Taxa base: usa a regra com maior score de confiança
    base_rate = 0.0
    if base_rules:
        best_base = max(base_rules, key=lambda r: r.confidence_score)
        base_rate = best_base.rate_pct or 0.0
        if len(base_rules) > 1:
            notes.append(
                f"{len(base_rules)} regras base encontradas; "
                f"usando '{best_base.product or best_base.rule_type}' "
                f"(maior confiança: {best_base.confidence_score:.2f})."
            )
    else:
        notes.append("Nenhuma taxa base encontrada para este produto/segmento.")

    # Soma ajustes
    total_adjustment = sum(r.rate_pct or 0.0 for r in adj_rules)

    # Taxa total percentual
    total_rate = base_rate + total_adjustment

    # Taxa fixa total
    total_fixed = sum(r.fixed_fee_amount or 0.0 for r in fixed_rules)

    # Aplicar cap/floor
    effective_cap = None
    for cap_rule in limit_rules:
        if cap_rule.cap_amount is not None:
            effective_cap = cap_rule.cap_amount
            if request.transaction_amount:
                fee_from_rate = request.transaction_amount * (total_rate / 100)
                if fee_from_rate > cap_rule.cap_amount:
                    notes.append(
                        f"Cap de R$ {cap_rule.cap_amount:.2f} aplicado "
                        f"(taxa calculada seria R$ {fee_from_rate:.2f})."
                    )

    # Calcular valor absoluto estimado
    estimated_fee = None
    if request.transaction_amount and request.transaction_amount > 0:
        fee_from_rate = request.transaction_amount * (total_rate / 100)
        if effective_cap:
            fee_from_rate = min(fee_from_rate, effective_cap)
        estimated_fee = round(fee_from_rate + total_fixed, 4)

    # Montar regras usadas na simulação
    matched = base_rules[:1] + adj_rules + fixed_rules + limit_rules

    notes.append(
        f"Taxa base: {base_rate:.2f}% | "
        f"Ajustes: {total_adjustment:+.2f}% | "
        f"Taxa efetiva: {total_rate:.2f}%"
    )

    if adj_rules:
        adj_desc = ", ".join(r.rule_type for r in adj_rules)
        notes.append(f"Ajustes aplicados: {adj_desc}")

    return SimulationResponse(
        matched_rules=matched,
        total_rate_pct=round(total_rate, 4),
        total_fixed_fee=round(total_fixed, 4),
        effective_cap=effective_cap,
        estimated_fee_amount=estimated_fee,
        notes=notes,
    )


def compare_networks(
    rules: list[RuleCandidate],
    base_request: SimulationRequest,
    networks: list[str] | None = None,
) -> dict[str, SimulationResponse]:
    """
    Compara taxas entre múltiplas Bandeiras para a mesma transação.

    Args:
        rules:        Todas as regras disponíveis.
        base_request: Request base (o campo network será sobrescrito).
        networks:     Lista de bandeiras a comparar (padrão: todas disponíveis).

    Returns:
        Dict mapeando nome da bandeira → SimulationResponse.
    """
    if networks is None:
        networks = list({r.network for r in rules})

    results: dict[str, SimulationResponse] = {}
    for net in sorted(networks):
        net_request = base_request.model_copy(update={"network": net})
        results[net] = simulate(rules, net_request)

    return results
