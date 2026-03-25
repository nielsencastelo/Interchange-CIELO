"""
tests/test_patterns.py
======================
Testes unitários para src/extract/patterns.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.extract.patterns import (
    find_brl_values, find_cap, find_installment_band,
    find_percentages, is_atm, is_cnp, is_contactless,
    is_installment, is_prepaid, normalize_text, parse_number,
)


class TestParseNumber:
    def test_brazilian_decimal(self):
        assert parse_number("1,17") == 1.17

    def test_us_decimal(self):
        assert parse_number("1.73") == 1.73

    def test_brazilian_thousands(self):
        assert parse_number("1.200,50") == 1200.50

    def test_negative(self):
        assert parse_number("-0,27") == -0.27

    def test_integer(self):
        assert parse_number("8") == 8.0


class TestFindPercentages:
    def test_single_percentage(self):
        result = find_percentages("Taxa base de 1,17% para Classic")
        assert result == [1.17]

    def test_multiple_percentages(self):
        result = find_percentages("De 1,73% a 2,08% dependendo do produto")
        assert len(result) == 2
        assert 1.73 in result
        assert 2.08 in result

    def test_negative_percentage(self):
        result = find_percentages("Ajuste de -0,27% para supermercados")
        assert result == [-0.27]

    def test_positive_sign(self):
        result = find_percentages("Acréscimo de +0,35% para parcelado")
        assert result == [0.35]

    def test_no_percentage(self):
        result = find_percentages("Texto sem percentual nenhum aqui")
        assert result == []


class TestFindBrlValues:
    def test_basic_brl(self):
        result = find_brl_values("Taxa fixa de R$ 8,00 por saque")
        assert result == [8.0]

    def test_brl_without_space(self):
        result = find_brl_values("Teto de R$0,35 por transação")
        assert result == [0.35]

    def test_no_brl(self):
        result = find_brl_values("Taxa de 1,73%")
        assert result == []


class TestFindInstallmentBand:
    def test_dash_format(self):
        assert find_installment_band("Para parcelas 2-6") == "2-6"

    def test_a_format(self):
        assert find_installment_band("De 7 a 12 parcelas") == "7-12"

    def test_21_parcelas(self):
        assert find_installment_band("Parcelas 7-21") == "7-21"

    def test_no_band(self):
        assert find_installment_band("Transação à vista") is None

    def test_em_dash(self):
        assert find_installment_band("Parcelas 2–6") == "2-6"


class TestFindCap:
    def test_limitado_a(self):
        result = find_cap("Taxa limitada a R$ 0,35 por transação")
        assert result == 0.35

    def test_teto(self):
        result = find_cap("Teto de R$ 0,30 aplicável")
        assert result == 0.30

    def test_no_cap(self):
        result = find_cap("Taxa de 1,17% sem teto")
        assert result is None


class TestBooleanDetectors:
    def test_contactless(self):
        assert is_contactless("Transação contactless NFC") is True
        assert is_contactless("Cartão presente normal") is False

    def test_cnp(self):
        assert is_cnp("Cartão não presente e-commerce") is True
        assert is_cnp("Transação no PDV") is False
        assert is_cnp("Verified by Visa VbV") is True

    def test_atm(self):
        assert is_atm("Saque em caixa eletrônico") is True
        assert is_atm("ATM doméstico") is True
        assert is_atm("Compra no débito") is False

    def test_prepaid(self):
        assert is_prepaid("Cartão pré-pago") is True
        assert is_prepaid("Consumer Prepaid") is True
        assert is_prepaid("Cartão crédito") is False

    def test_installment(self):
        assert is_installment("Transação parcelada 6x") is True
        assert is_installment("Pagamento à vista") is False


class TestNormalizeText:
    def test_non_breaking_space(self):
        result = normalize_text("Taxa\xa0de\xa01,17%")
        assert "\xa0" not in result
        assert "Taxa de 1,17%" == result

    def test_multiple_spaces(self):
        result = normalize_text("Taxa   base   de   1,17%")
        assert result == "Taxa base de 1,17%"

    def test_newlines(self):
        result = normalize_text("Linha 1\nLinha 2\nLinha 3")
        assert "\n" not in result
