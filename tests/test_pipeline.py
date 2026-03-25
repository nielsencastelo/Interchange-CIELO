"""
tests/test_pipeline.py
======================
Testes de integração do pipeline de extração.
Não requerem banco de dados nem API keys.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from src.pipeline import _deduplicate, chunk_page_text, extract_from_document
from src.schemas import ExtractResult, RuleCandidate


class TestChunkPageText:
    def test_empty(self):
        assert chunk_page_text("") == []

    def test_short_text_single_chunk(self):
        # Text must be >= CHUNK_MIN_CHARS (30) to appear as a chunk
        result = chunk_page_text("Taxa de intercâmbio de 1,17% para Classic crédito PF", max_chars=800)
        assert len(result) == 1
        assert "1,17" in result[0]

    def test_long_text_splits(self):
        long_text = "Taxa de 1,17% para Classic.\n" * 20
        result = chunk_page_text(long_text, max_chars=100)
        assert len(result) > 1

    def test_ignores_empty_lines(self):
        text = "Linha 1\n\n\n\nLinha 2\n"
        result = chunk_page_text(text, max_chars=800)
        for chunk in result:
            assert chunk.strip() != ""

    def test_respects_min_chars(self):
        text = "ok\n" * 10
        result = chunk_page_text(text, max_chars=800)
        for chunk in result:
            assert len(chunk) >= 30 or len(text) < 30


class TestDeduplicate:
    def make_rule(self, rate_pct: float, score: float = 0.70) -> RuleCandidate:
        return RuleCandidate(
            network="Visa", region="BR", rule_type="base_rate",
            card_family="credit", rate_pct=rate_pct,
            evidence_text="sample", confidence_score=score,
        )

    def test_removes_exact_duplicates(self):
        rules = [self.make_rule(1.17), self.make_rule(1.17)]
        result = _deduplicate(rules)
        assert len(result) == 1

    def test_keeps_higher_score_on_duplicate(self):
        rules = [self.make_rule(1.17, score=0.55), self.make_rule(1.17, score=0.85)]
        result = _deduplicate(rules)
        assert result[0].confidence_score == 0.85

    def test_keeps_distinct_rates(self):
        rules = [self.make_rule(1.17), self.make_rule(1.73), self.make_rule(1.83)]
        result = _deduplicate(rules)
        assert len(result) == 3

    def test_empty_list(self):
        assert _deduplicate([]) == []


class TestExtractFromDocument:
    def _write_temp(self, content: str, suffix: str = ".txt") -> Path:
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix, mode="w", encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_returns_extract_result(self):
        f = self._write_temp("Taxa de intercâmbio 1,17% crédito Visa\n")
        result = extract_from_document(f, network="Visa")
        assert isinstance(result, ExtractResult)
        f.unlink(missing_ok=True)

    def test_extracts_rules_from_text(self):
        content = (
            "Taxa base crédito pessoa física Classic 1,17%\n"
            "Taxa base crédito pessoa física Platinum 1,73%\n"
            "Saque ATM taxa fixa R$ 8,00\n"
        )
        f = self._write_temp(content)
        result = extract_from_document(f, network="Visa")
        assert len(result.rules) > 0
        f.unlink(missing_ok=True)

    def test_network_assigned(self):
        f = self._write_temp("Taxa Mastercard 1,20% crédito\n")
        result = extract_from_document(f, network="Mastercard")
        for rule in result.rules:
            assert rule.network == "Mastercard"
        f.unlink(missing_ok=True)

    def test_empty_file_returns_warning(self):
        f = self._write_temp("")
        result = extract_from_document(f, network="Visa")
        assert len(result.warnings) > 0
        f.unlink(missing_ok=True)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_from_document("/nonexistent/path/file.txt", network="Visa")

    def test_amex_network(self):
        content = "American Express Platinum 2,10% crédito pessoa física\n"
        f = self._write_temp(content)
        result = extract_from_document(f, network="AmericanExpress")
        assert result.network == "AmericanExpress"
        f.unlink(missing_ok=True)

    def test_deduplication_applied(self):
        # Mesma taxa repetida em várias linhas
        content = "Taxa 1,73% crédito\n" * 10
        f = self._write_temp(content)
        result = extract_from_document(f, network="Visa")
        # Deve deduplicar para no máximo 1 regra por taxa única
        rates = [r.rate_pct for r in result.rules if r.rate_pct is not None]
        assert len(set(rates)) == len(rates) or len(result.rules) < 10
        f.unlink(missing_ok=True)
