"""
tests/conftest.py
=================
Fixtures compartilhadas entre todos os testes.

Usa banco SQLite em memória para isolamento total —
nenhum teste precisa de PostgreSQL ou Docker.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Garante que src/ está no path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Força SQLite em memória para todos os testes
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ENABLE_LLM_NORMALIZATION", "false")


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """Inicializa banco SQLite em memória uma vez por sessão de testes."""
    from src.database import init_db
    init_db()
    yield


@pytest.fixture
def sample_rules():
    """Retorna lista de regras de amostra para testes de simulação."""
    from src.schemas import RuleCandidate

    return [
        RuleCandidate(network="Visa", region="BR", rule_type="base_rate",
                      audience="PF", card_family="credit", product="Classic",
                      merchant_group="base", channel="cp", installment_band="avista",
                      rate_pct=1.17, evidence_text="Taxa Visa Classic", confidence_score=0.95),
        RuleCandidate(network="Visa", region="BR", rule_type="base_rate",
                      audience="PF", card_family="credit", product="Platinum",
                      merchant_group="base", channel="cp", installment_band="avista",
                      rate_pct=1.73, evidence_text="Taxa Visa Platinum", confidence_score=0.95),
        RuleCandidate(network="Visa", region="BR", rule_type="merchant_adjustment",
                      audience="PF", card_family="credit",
                      merchant_group="supermercados", channel="cp",
                      rate_pct=-0.27, evidence_text="Ajuste supermercados", confidence_score=0.90),
        RuleCandidate(network="Mastercard", region="BR", rule_type="base_rate",
                      audience="PF", card_family="credit", product="Gold",
                      merchant_group="base", channel="cp", installment_band="avista",
                      rate_pct=1.20, evidence_text="Taxa MC Gold", confidence_score=0.95),
        RuleCandidate(network="AmericanExpress", region="BR", rule_type="base_rate",
                      audience="PF", card_family="credit", product="Platinum",
                      merchant_group="base", channel="cp", installment_band="avista",
                      rate_pct=2.10, evidence_text="Taxa Amex Platinum", confidence_score=0.95),
        RuleCandidate(network="Elo", region="BR", rule_type="base_rate",
                      audience="PF", card_family="credit", product="Grafite",
                      merchant_group="base", channel="cp", installment_band="avista",
                      rate_pct=1.62, evidence_text="Taxa Elo Grafite", confidence_score=0.95),
        RuleCandidate(network="Hipercard", region="BR", rule_type="base_rate",
                      audience="PF", card_family="credit", product="Hipercard_Standard",
                      merchant_group="base", channel="cp", installment_band="avista",
                      rate_pct=1.25, evidence_text="Taxa Hipercard Standard", confidence_score=0.90),
    ]


@pytest.fixture
def csv_path():
    """Retorna o caminho para o CSV de amostra."""
    path = Path(__file__).resolve().parents[1] / "data" / "sample_interchange_rules.csv"
    if not path.exists():
        pytest.skip("CSV de amostra não encontrado")
    return path
