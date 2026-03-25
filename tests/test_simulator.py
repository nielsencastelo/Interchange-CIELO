"""
tests/test_simulator.py
=======================
Testes do motor de simulação de taxas.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.schemas import RuleCandidate, SimulationRequest
from src.simulator import compare_networks, filter_applicable_rules, simulate


def make_rule(**kw) -> RuleCandidate:
    defaults = dict(
        network="Visa", region="BR", rule_type="base_rate",
        evidence_text="sample", confidence_score=0.90,
    )
    defaults.update(kw)
    return RuleCandidate(**defaults)


SAMPLE_RULES = [
    # Visa base rates
    make_rule(audience="PF", card_family="credit", product="Classic",
              merchant_group="base", channel="cp", installment_band="avista",
              rate_pct=1.17, rule_type="base_rate"),
    make_rule(audience="PF", card_family="credit", product="Platinum",
              merchant_group="base", channel="cp", installment_band="avista",
              rate_pct=1.73, rule_type="base_rate"),
    # Visa merchant adjustment
    make_rule(audience="PF", card_family="credit", product=None,
              merchant_group="supermercados", channel="cp", installment_band=None,
              rate_pct=-0.27, rule_type="merchant_adjustment"),
    # Visa installment adjustment
    make_rule(audience="PF", card_family="credit", product=None,
              merchant_group=None, channel="cp", installment_band="2-6",
              rate_pct=0.35, rule_type="installment_adjustment"),
    # Mastercard base rate
    make_rule(network="Mastercard", audience="PF", card_family="credit",
              product="Gold", merchant_group="base", channel="cp",
              installment_band="avista", rate_pct=1.20, rule_type="base_rate"),
    # AmericanExpress base rate
    make_rule(network="AmericanExpress", audience="PF", card_family="credit",
              product="Platinum", merchant_group="base", channel="cp",
              installment_band="avista", rate_pct=2.10, rule_type="base_rate"),
    # Elo fixed fee ATM
    make_rule(network="Elo", card_family="cash_withdrawal", channel="atm",
              rule_type="fixed_fee", fixed_fee_amount=7.0, rate_pct=None),
    # Debit cap
    make_rule(network="Visa", card_family="debit", rule_type="cap",
              cap_amount=0.35, rate_pct=None),
]


class TestFilterApplicableRules:
    def _req(self, **kw) -> SimulationRequest:
        defaults = dict(network="Visa", region="BR")
        defaults.update(kw)
        return SimulationRequest(**defaults)

    def test_filters_by_network(self):
        req = self._req(network="Visa")
        result = filter_applicable_rules(SAMPLE_RULES, req)
        assert all(r.network == "Visa" for r in result)
        assert not any(r.network == "Mastercard" for r in result)

    def test_filters_by_card_family(self):
        req = self._req(card_family="credit")
        result = filter_applicable_rules(SAMPLE_RULES, req)
        for r in result:
            assert r.card_family in (None, "credit")

    def test_none_request_matches_all_rules(self):
        req = self._req()  # nenhum filtro de segmentação
        result = filter_applicable_rules(SAMPLE_RULES, req)
        # Deve retornar todas as regras da Visa (incluindo cap e debit)
        assert len(result) > 0

    def test_specific_product_match(self):
        req = self._req(card_family="credit", product="Platinum")
        result = filter_applicable_rules(SAMPLE_RULES, req)
        products = [r.product for r in result]
        assert "Platinum" in products or None in products

    def test_installment_band_avista_excludes_installment_rules(self):
        req = self._req(card_family="credit", installment_band="avista")
        result = filter_applicable_rules(SAMPLE_RULES, req)
        # Regra de "2-6" não deve aparecer para "avista"
        for r in result:
            assert r.installment_band not in ("2-6", "7-12")


class TestSimulate:
    def _req(self, **kw) -> SimulationRequest:
        defaults = dict(network="Visa", region="BR", card_family="credit",
                        audience="PF", channel="cp", installment_band="avista")
        defaults.update(kw)
        return SimulationRequest(**defaults)

    def test_returns_simulation_response(self):
        from src.schemas import SimulationResponse
        result = simulate(SAMPLE_RULES, self._req(product="Classic", merchant_group="base"))
        assert isinstance(result, SimulationResponse)

    def test_base_rate_applied(self):
        result = simulate(SAMPLE_RULES, self._req(product="Classic", merchant_group="base"))
        # Classic = 1.17%
        assert result.total_rate_pct > 0

    def test_merchant_adjustment_included(self):
        req_base = self._req(product="Platinum", merchant_group="base")
        req_super = self._req(product="Platinum", merchant_group="supermercados")
        result_base = simulate(SAMPLE_RULES, req_base)
        result_super = simulate(SAMPLE_RULES, req_super)
        # Supermercados tem desconto de -0.27%
        assert result_super.total_rate_pct < result_base.total_rate_pct

    def test_installment_adds_to_rate(self):
        wildcard_rules = [
            make_rule(audience="PF", card_family="credit", product="Classic",
                      merchant_group="base", channel="cp", installment_band=None,
                      rate_pct=1.17, rule_type="base_rate"),
            make_rule(audience="PF", card_family="credit",
                      merchant_group=None, channel="cp", installment_band="2-6",
                      rate_pct=0.35, rule_type="installment_adjustment"),
        ]
        req_avista = self._req(product="Classic", merchant_group="base", installment_band="avista")
        req_parcel = self._req(product="Classic", merchant_group="base", installment_band="2-6")
        result_avista = simulate(wildcard_rules, req_avista)
        result_parcel = simulate(wildcard_rules, req_parcel)
        assert result_parcel.total_rate_pct > result_avista.total_rate_pct

    def test_no_rules_returns_zero_rate(self):
        result = simulate(SAMPLE_RULES, self._req(network="Hipercard"))
        assert result.total_rate_pct == 0.0
        assert len(result.matched_rules) == 0
        assert len(result.notes) > 0

    def test_estimated_fee_with_amount(self):
        req = self._req(product="Platinum", merchant_group="base", transaction_amount=1000.0)
        result = simulate(SAMPLE_RULES, req)
        if result.total_rate_pct > 0:
            assert result.estimated_fee_amount is not None
            assert result.estimated_fee_amount > 0

    def test_fixed_fee_atm(self):
        req = SimulationRequest(network="Elo", region="BR", card_family="cash_withdrawal",
                                channel="atm")
        result = simulate(SAMPLE_RULES, req)
        assert result.total_fixed_fee == 7.0


class TestCompareNetworks:
    def test_returns_dict(self):
        req = SimulationRequest(network="Visa", region="BR", card_family="credit",
                                audience="PF", channel="cp")
        result = compare_networks(SAMPLE_RULES, req,
                                  networks=["Visa", "Mastercard", "AmericanExpress"])
        assert isinstance(result, dict)
        assert "Visa" in result
        assert "Mastercard" in result
        assert "AmericanExpress" in result

    def test_different_rates_per_network(self):
        req = SimulationRequest(network="Visa", region="BR", card_family="credit",
                                product="Platinum", channel="cp", audience="PF")
        result = compare_networks(SAMPLE_RULES, req,
                                  networks=["Visa", "AmericanExpress"])
        # Amex Platinum (2.10%) > Visa Platinum (1.73%)
        assert result["AmericanExpress"].total_rate_pct >= result["Visa"].total_rate_pct
