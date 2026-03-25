"""
src/seed_sample_data.py
=======================
Carga de dados de amostra no banco de dados.

Lê o arquivo data/sample_interchange_rules.csv e popula o banco
com regras reais de Visa, Mastercard, American Express, Elo,
Hipercard e limites regulatórios do Banco Central do Brasil.

Uso:
    python -m src.seed_sample_data

    # Para resetar e recarregar:
    python -m src.seed_sample_data --reset
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from .config import BASE_DIR, settings
from .database import init_db
from .repository import count_rules, delete_all, save_rules
from .schemas import RuleCandidate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Redes incluídas no CSV de amostra
ALL_NETWORKS = ["Visa", "Mastercard", "AmericanExpress", "Elo", "Hipercard", "BCB_Limite"]


def load_csv(csv_path: str) -> list[RuleCandidate]:
    """
    Lê o CSV de amostra e converte para lista de RuleCandidate.

    Args:
        csv_path: Caminho para o arquivo CSV.

    Returns:
        Lista de RuleCandidate prontos para persistência.
    """

    def _safe(val) -> str | None:
        if pd.isna(val) or str(val).strip() in ("", "nan"):
            return None
        return str(val).strip()

    def _safe_float(val) -> float | None:
        if pd.isna(val):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    df = pd.read_csv(csv_path)
    rules: list[RuleCandidate] = []

    for row in df.itertuples(index=False):
        try:
            rule = RuleCandidate(
                network=str(row.network),
                region=str(row.region),
                audience=_safe(row.audience),
                card_family=_safe(row.card_family),
                product=_safe(row.product),
                merchant_group=_safe(row.merchant_group),
                channel=_safe(row.channel),
                installment_band=_safe(row.installment_band),
                rule_type=str(row.rule_type),
                rate_pct=_safe_float(row.rate_pct),
                fixed_fee_amount=_safe_float(row.fixed_fee_brl),
                currency="BRL",
                cap_amount=_safe_float(row.cap_brl),
                floor_amount=None,
                evidence_text=str(row.notes),
                confidence_score=0.95,  # Dados validados manualmente
                metadata={"seed": True, "source": "sample_interchange_rules.csv"},
            )
            rules.append(rule)
        except Exception as e:
            logger.warning("Linha ignorada (erro): %s | %s", e, row)

    return rules


def main(reset: bool = False) -> None:
    """
    Executa a carga dos dados de amostra.

    Args:
        reset: Se True, apaga todos os dados antes de recarregar.
    """
    logger.info("=" * 60)
    logger.info("INTERCHANGE AI — CARGA DE DADOS DE AMOSTRA")
    logger.info("=" * 60)

    # Inicializa banco
    init_db()
    logger.info("Banco de dados inicializado.")

    # Opcional: reset
    if reset:
        removed = delete_all()
        logger.info("Reset: %d regras removidas.", removed)

    # Verifica se já há dados
    existing = count_rules()
    if existing > 0 and not reset:
        logger.info(
            "Banco já contém %d regras. Use --reset para recarregar.", existing
        )
        return

    # Caminho do CSV
    csv_path = BASE_DIR / settings.sample_csv_path
    if not csv_path.exists():
        logger.error("CSV não encontrado: %s", csv_path)
        sys.exit(1)

    logger.info("Lendo: %s", csv_path)
    rules = load_csv(str(csv_path))
    logger.info("Regras lidas do CSV: %d", len(rules))

    # Estatísticas por rede
    by_network: dict[str, int] = {}
    for rule in rules:
        by_network[rule.network] = by_network.get(rule.network, 0) + 1

    # Salva no banco
    count = save_rules(rules, version_tag="sample-2024-Q1")

    logger.info("-" * 40)
    logger.info("REGRAS CARREGADAS POR BANDEIRA:")
    for net, n in sorted(by_network.items()):
        logger.info("  %-20s %d", net, n)
    logger.info("-" * 40)
    logger.info("TOTAL: %d regras carregadas com sucesso.", count)
    logger.info("=" * 60)
    logger.info("Próximos passos:")
    logger.info("  uvicorn src.api.main:app --reload --port 8000")
    logger.info("  streamlit run src/dashboard.py")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carrega dados de amostra no banco.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Apaga todos os dados antes de recarregar",
    )
    args = parser.parse_args()
    main(reset=args.reset)
