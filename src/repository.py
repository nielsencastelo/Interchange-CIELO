"""
src/repository.py
=================
Camada de acesso a dados (Repository Pattern).

Todas as operações de banco de dados passam por este módulo,
garantindo separação entre lógica de negócio e persistência.

Funções:
    save_rules(rules)          → int  (contagem de regras salvas)
    list_rules(filters)        → list[RuleCandidate]
    count_rules()              → int
    get_stats()                → dict
    delete_all()               → int
    save_extraction_log(...)   → None
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from .database import ExtractionLog, RuleRecord, SessionLocal
from .schemas import RuleCandidate

logger = logging.getLogger(__name__)


def save_rules(rules: list[RuleCandidate], version_tag: str | None = None) -> int:
    """
    Persiste uma lista de regras no banco de dados.

    Args:
        rules:       Lista de RuleCandidate validados.
        version_tag: Tag de versão opcional (ex: "2024-Q1").

    Returns:
        Número de regras salvas com sucesso.
    """
    if not rules:
        return 0

    count = 0
    with SessionLocal() as session:
        for rule in rules:
            record = RuleRecord(
                network=rule.network,
                region=rule.region,
                rule_type=rule.rule_type,
                audience=rule.audience,
                card_family=rule.card_family,
                product=rule.product,
                merchant_group=rule.merchant_group,
                channel=rule.channel,
                installment_band=rule.installment_band,
                rate_pct=rule.rate_pct,
                fixed_fee_amount=rule.fixed_fee_amount,
                currency=rule.currency,
                cap_amount=rule.cap_amount,
                floor_amount=rule.floor_amount,
                effective_from=str(rule.effective_from) if rule.effective_from else None,
                effective_to=str(rule.effective_to) if rule.effective_to else None,
                evidence_text=rule.evidence_text,
                page_number=rule.page_number,
                confidence_score=rule.confidence_score,
                metadata_json=rule.metadata,
                version_tag=version_tag,
            )
            session.add(record)
            count += 1
        session.commit()

    logger.info("save_rules: %d regras persistidas.", count)
    return count


def list_rules(
    network: str | None = None,
    card_family: str | None = None,
    rule_type: str | None = None,
    audience: str | None = None,
    product: str | None = None,
    merchant_group: str | None = None,
    channel: str | None = None,
    min_confidence: float = 0.0,
    region: str = "BR",
    limit: int = 1000,
) -> list[RuleCandidate]:
    """
    Lista regras do banco com filtros opcionais.

    Args:
        network:        Filtrar por bandeira.
        card_family:    Filtrar por família de cartão.
        rule_type:      Filtrar por tipo de regra.
        audience:       Filtrar por público (PF/PJ/ALL).
        product:        Filtrar por produto.
        merchant_group: Filtrar por segmento de comércio.
        channel:        Filtrar por canal.
        min_confidence: Score mínimo de confiança.
        region:         Região (padrão BR).
        limit:          Máximo de registros retornados.

    Returns:
        Lista de RuleCandidate.
    """
    with SessionLocal() as session:
        stmt = select(RuleRecord).where(RuleRecord.region == region)

        if network:
            stmt = stmt.where(RuleRecord.network == network)
        if card_family:
            stmt = stmt.where(RuleRecord.card_family == card_family)
        if rule_type:
            stmt = stmt.where(RuleRecord.rule_type == rule_type)
        if audience:
            stmt = stmt.where(RuleRecord.audience == audience)
        if product:
            stmt = stmt.where(RuleRecord.product == product)
        if merchant_group:
            stmt = stmt.where(RuleRecord.merchant_group == merchant_group)
        if channel:
            stmt = stmt.where(RuleRecord.channel == channel)
        if min_confidence > 0:
            stmt = stmt.where(RuleRecord.confidence_score >= min_confidence)

        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    return [_record_to_candidate(r) for r in rows]


def get_all_rules() -> list[RuleCandidate]:
    """Retorna todas as regras do banco (sem filtros)."""
    return list_rules(limit=10000)


def count_rules() -> int:
    """Retorna a contagem total de regras no banco."""
    with SessionLocal() as session:
        return session.execute(select(func.count(RuleRecord.id))).scalar_one()


def get_stats() -> dict[str, Any]:
    """
    Retorna estatísticas agregadas da base de regras.

    Returns:
        Dict com:
            total, por_network, por_rule_type, por_card_family,
            avg_confidence, high_confidence_count, low_confidence_count
    """
    with SessionLocal() as session:
        total = session.execute(select(func.count(RuleRecord.id))).scalar_one()

        # Por bandeira
        por_network = dict(
            session.execute(
                select(RuleRecord.network, func.count(RuleRecord.id))
                .group_by(RuleRecord.network)
            ).all()
        )

        # Por tipo de regra
        por_rule_type = dict(
            session.execute(
                select(RuleRecord.rule_type, func.count(RuleRecord.id))
                .group_by(RuleRecord.rule_type)
            ).all()
        )

        # Por família de cartão
        por_card_family = dict(
            session.execute(
                select(RuleRecord.card_family, func.count(RuleRecord.id))
                .group_by(RuleRecord.card_family)
            ).all()
        )

        # Score médio de confiança
        avg_confidence = session.execute(
            select(func.avg(RuleRecord.confidence_score))
        ).scalar_one() or 0.0

        # Alta confiança (>= 0.70)
        high_conf = session.execute(
            select(func.count(RuleRecord.id)).where(RuleRecord.confidence_score >= 0.70)
        ).scalar_one()

        # Baixa confiança (< 0.50)
        low_conf = session.execute(
            select(func.count(RuleRecord.id)).where(RuleRecord.confidence_score < 0.50)
        ).scalar_one()

    return {
        "total": total,
        "por_network": por_network,
        "por_rule_type": por_rule_type,
        "por_card_family": por_card_family,
        "avg_confidence": round(float(avg_confidence), 3),
        "high_confidence_count": high_conf,
        "low_confidence_count": low_conf,
    }


def delete_all(network: str | None = None) -> int:
    """
    Remove todas as regras (ou apenas as de uma rede específica).

    Args:
        network: Se informado, remove apenas regras desta rede.

    Returns:
        Número de registros removidos.
    """
    with SessionLocal() as session:
        stmt = select(RuleRecord)
        if network:
            stmt = stmt.where(RuleRecord.network == network)
        rows = session.execute(stmt).scalars().all()
        count = len(rows)
        for row in rows:
            session.delete(row)
        session.commit()

    logger.info("delete_all: %d regras removidas (network=%s).", count, network or "ALL")
    return count


def save_extraction_log(
    source_path: str,
    network: str,
    region: str,
    total_rules: int,
    high_confidence: int,
    low_confidence: int,
    warnings: list[str],
    status: str = "success",
) -> None:
    """Registra log de uma execução do pipeline."""
    with SessionLocal() as session:
        log = ExtractionLog(
            source_path=source_path,
            network=network,
            region=region,
            total_rules=total_rules,
            high_confidence=high_confidence,
            low_confidence=low_confidence,
            warnings="\n".join(warnings),
            status=status,
        )
        session.add(log)
        session.commit()


def _record_to_candidate(r: RuleRecord) -> RuleCandidate:
    """Converte RuleRecord (ORM) em RuleCandidate (schema)."""
    return RuleCandidate(
        network=r.network,
        region=r.region,
        rule_type=r.rule_type,
        audience=r.audience,
        card_family=r.card_family,
        product=r.product,
        merchant_group=r.merchant_group,
        channel=r.channel,
        installment_band=r.installment_band,
        rate_pct=r.rate_pct,
        fixed_fee_amount=r.fixed_fee_amount,
        currency=r.currency,
        cap_amount=r.cap_amount,
        floor_amount=r.floor_amount,
        evidence_text=r.evidence_text,
        page_number=r.page_number,
        confidence_score=r.confidence_score,
        metadata=r.metadata_json or {},
    )
