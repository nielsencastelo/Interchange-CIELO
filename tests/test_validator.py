"""
tests/test_validator.py
=======================
Testes unitários para src/validator.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.schemas import RuleCandidate
from src.validator import filter_by_confidence, get_confidence_label, validate_rule


def make_rule(**kwargs) -> RuleCandidate:
    defaults = dict(
        network="Visa", region="BR", rule_type="base_rate",
        evidence_text="taxa de intercâmbio crédito 1,73%",
        confidence_score=0.55,
    )
    defaults.update(kwargs)
    return RuleCandidate(**defaults)


class TestValidateRule:
    def test_returns_rule_candidate(self):
        rule = make_rule(rate_pct=1.73, card_family="credit")
        result = validate_rule(rule)
        assert isinstance(result, RuleCandidate)

    def test_rate_out_of_range_penalized(self):
        rule = make_rule(rate_pct=99.0, card_family="credit", rule_type="base_rate")
        result = validate_rule(rule)
        # Score should be significantly below starting point (0.55)
        assert result.confidence_score <= 0.40

    def test_negative_fixed_fee_penalized(self):
        rule = make_rule(fixed_fee_amount=-5.0, rule_type="fixed_fee")
        result = validate_rule(rule)
        assert result.confidence_score <= 0.30

    def test_short_evidence_penalized(self):
        rule = make_rule(evidence_text="x", rate_pct=1.17)
        result = validate_rule(rule)
        assert result.confidence_score <= 0.35

    def test_product_bonus(self):
        rule_without = make_rule(rate_pct=1.73, card_family="credit")
        rule_with = make_rule(rate_pct=1.73, card_family="credit", product="Platinum")
        score_without = validate_rule(rule_without).confidence_score
        score_with = validate_rule(rule_with).confidence_score
        assert score_with > score_without

    def test_merchant_group_bonus(self):
        rule_without = make_rule(rate_pct=1.17, card_family="credit")
        rule_with = make_rule(rate_pct=1.17, card_family="credit", merchant_group="supermercados")
        score_without = validate_rule(rule_without).confidence_score
        score_with = validate_rule(rule_with).confidence_score
        assert score_with > score_without

    def test_context_keyword_bonus(self):
        rule = make_rule(
            rate_pct=0.35,
            evidence_text="Ajuste parcelado 0,35% para crédito",
            rule_type="installment_adjustment",
        )
        result = validate_rule(rule)
        assert result.confidence_score > 0.55

    def test_score_stays_in_range(self):
        rule = make_rule(
            rate_pct=1.73,
            card_family="credit",
            product="Platinum",
            merchant_group="supermercados",
            channel="cp",
            audience="PF",
            evidence_text="taxa de intercâmbio parcelado crédito 1,73%",
            confidence_score=0.90,
        )
        result = validate_rule(rule)
        assert 0.0 <= result.confidence_score <= 1.0

    def test_debit_rate_in_range(self):
        rule = make_rule(rate_pct=0.50, card_family="debit", rule_type="base_rate")
        result = validate_rule(rule)
        assert result.confidence_score >= 0.50

    def test_debit_rate_above_bcb_limit_penalized(self):
        rule = make_rule(rate_pct=1.50, card_family="debit", rule_type="base_rate",
                         evidence_text="débito doméstico")
        result = validate_rule(rule)
        assert result.confidence_score <= 0.40


class TestFilterByConfidence:
    def test_filters_low(self):
        rules = [
            make_rule(confidence_score=0.30),
            make_rule(confidence_score=0.70),
            make_rule(confidence_score=0.85),
        ]
        result = filter_by_confidence(rules, min_score=0.50)
        assert len(result) == 2

    def test_empty_list(self):
        assert filter_by_confidence([], min_score=0.70) == []

    def test_zero_min_keeps_all(self):
        rules = [make_rule(confidence_score=0.10), make_rule(confidence_score=0.99)]
        assert len(filter_by_confidence(rules, min_score=0.0)) == 2


class TestGetConfidenceLabel:
    def test_alta(self):
        assert get_confidence_label(0.85) == "alta"
        assert get_confidence_label(1.0) == "alta"
        assert get_confidence_label(0.80) == "alta"

    def test_media(self):
        assert get_confidence_label(0.50) == "média"
        assert get_confidence_label(0.75) == "média"

    def test_baixa(self):
        assert get_confidence_label(0.30) == "baixa"
        assert get_confidence_label(0.0) == "baixa"
        assert get_confidence_label(0.49) == "baixa"
