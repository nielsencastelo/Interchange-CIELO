"""
tests/test_normalizer.py
========================
Testes unitários para src/normalizer.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.normalizer import (
    infer_audience, infer_card_family, infer_channel,
    infer_merchant_group, infer_product, infer_rule_type,
    normalize_snippet,
)


class TestInferRuleType:
    def test_contactless(self):
        assert infer_rule_type("Transação contactless NFC") == "contactless_adjustment"

    def test_cnp_authenticated(self):
        assert infer_rule_type("VbV autenticado ECI5") == "cnp_authenticated_adjustment"

    def test_cnp(self):
        assert infer_rule_type("Cartão não presente e-commerce") == "cnp_adjustment"

    def test_installment(self):
        assert infer_rule_type("Transação parcelada 6x") == "installment_adjustment"

    def test_atm(self):
        assert infer_rule_type("Saque em caixa ATM") == "fixed_fee"

    def test_cap(self):
        assert infer_rule_type("Taxa limitada a R$ 0,35") == "cap"

    def test_merchant_adjustment(self):
        assert infer_rule_type("Ajuste para supermercados MCC") == "merchant_adjustment"

    def test_base_rate_default(self):
        assert infer_rule_type("Taxa básica de 1,17%") == "base_rate"


class TestInferChannel:
    def test_atm(self):
        assert infer_channel("Saque em ATM doméstico") == "atm"

    def test_contactless(self):
        assert infer_channel("Pagamento contactless") == "cp_contactless"

    def test_cnp(self):
        assert infer_channel("Cartão não presente") == "cnp"

    def test_cp(self):
        assert infer_channel("Cartão presente no PDV cp") == "cp"

    def test_none(self):
        assert infer_channel("Texto genérico sem canal") is None


class TestInferCardFamily:
    def test_atm(self):
        assert infer_card_family("Saque ATM") == "cash_withdrawal"

    def test_prepaid(self):
        assert infer_card_family("Cartão pré-pago consumer") == "prepaid"

    def test_debit(self):
        assert infer_card_family("Transação débito automático") == "debit"

    def test_credit(self):
        assert infer_card_family("Crédito rotativo") == "credit"

    def test_none(self):
        assert infer_card_family("Texto qualquer") is None


class TestInferProduct:
    def test_visa_infinite(self):
        assert infer_product("Produto Visa Infinite premium") == "Infinite"

    def test_visa_platinum(self):
        assert infer_product("Visa Platinum") == "Platinum"

    def test_mc_black(self):
        assert infer_product("Mastercard Black") == "Black"

    def test_mc_world_legend(self):
        assert infer_product("World Legend Mastercard") == "World_Legend"

    def test_amex_centurion(self):
        # Centurion não está no map — expectativa: None ou "Black"
        result = infer_product("American Express Centurion Black card")
        assert result in (None, "Black")  # Black aparece antes de Centurion no mapa

    def test_atm_tier(self):
        assert infer_product("ATM Tier I doméstico") == "ATM_Tier_I"

    def test_none(self):
        assert infer_product("Texto sem produto identificável") is None


class TestInferAudience:
    def test_pf(self):
        assert infer_audience("Taxa para pessoa física consumidora") == "PF"

    def test_pj(self):
        assert infer_audience("Cartão pessoa jurídica empresarial") == "PJ"

    def test_pf_abbreviation(self):
        assert infer_audience("Portador pf crédito") == "PF"

    def test_none(self):
        assert infer_audience("Texto sem audiência") is None


class TestInferMerchantGroup:
    def test_supermercados(self):
        assert infer_merchant_group("Rede de supermercados e hipermercados") == "supermercados"

    def test_hoteis(self):
        result = infer_merchant_group("Hotel e pousada categoria especial")
        assert result == "hoteis_aluguel_carros_turismo_joalherias_telemarketing"

    def test_postos(self):
        result = infer_merchant_group("Posto de combustível e farmácia")
        assert result == "postos_farmacias_departamento_aereas"

    def test_outros(self):
        assert infer_merchant_group("Outros estabelecimentos") == "outros"

    def test_none(self):
        assert infer_merchant_group("Texto qualquer sem segmento") is None


class TestNormalizeSnippet:
    def test_returns_list(self):
        result = normalize_snippet("Taxa de 1,17% para Classic", network="Visa")
        assert isinstance(result, list)

    def test_extracts_percentage(self):
        result = normalize_snippet("Taxa base de 1,17% crédito", network="Visa")
        assert len(result) > 0
        assert any(r.rate_pct == 1.17 for r in result)

    def test_network_set(self):
        result = normalize_snippet("Taxa de 1,73%", network="Mastercard")
        assert all(r.network == "Mastercard" for r in result)

    def test_atm_fixed_fee(self):
        result = normalize_snippet("Saque ATM taxa fixa de R$ 8,00", network="Visa")
        fixed = [r for r in result if r.rule_type == "fixed_fee"]
        assert len(fixed) > 0
        assert any(r.fixed_fee_amount == 8.0 for r in fixed)

    def test_empty_text(self):
        result = normalize_snippet("", network="Visa")
        assert result == []

    def test_confidence_score_range(self):
        result = normalize_snippet("Taxa parcelada 1,73% para 2-6x", network="Visa")
        for r in result:
            assert 0.0 <= r.confidence_score <= 1.0
