"""
src/pipeline.py
===============
Orquestrador principal do pipeline de extração de regras de intercâmbio.

Fluxo do pipeline:
    1. Ingestão: lê PDF, TXT ou HTML
    2. Segmentação: divide em chunks por página/bloco
    3. Extração regex: normalize_snippet() para cada chunk
    4. Extração LLM: normalize_with_llm() se habilitado
    5. Deduplicação: remove regras idênticas
    6. Validação: ajusta scores de confiança
    7. Persistência (opcional): save_rules()
    8. Log de execução

Uso via CLI:
    python -m src.pipeline --input manual.pdf --network Visa --region BR --save
    python -m src.pipeline --input data/visa_sample.txt --network Visa --save --use-llm

Uso via Python:
    from src.pipeline import extract_from_document
    result = extract_from_document("manual.pdf", network="Mastercard")
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .extract.llm_normalizer import normalize_with_llm
from .extract.pdf_reader import extract_text_pages
from .normalizer import normalize_snippet
from .schemas import ExtractResult, RuleCandidate
from .validator import validate_rule

logger = logging.getLogger(__name__)

# Redes suportadas pelo pipeline
SUPPORTED_NETWORKS = ["Visa", "Mastercard", "AmericanExpress", "Elo", "Hipercard"]

# Tamanho máximo de chunk em caracteres para envio ao LLM
CHUNK_MAX_CHARS = 800

# Tamanho mínimo de chunk para ser processado
CHUNK_MIN_CHARS = 30


def chunk_page_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """
    Divide o texto de uma página em chunks para processamento.

    Estratégia:
        - Divide por linhas
        - Agrupa linhas até atingir max_chars
        - Evita quebrar no meio de uma linha

    Args:
        text:      Texto completo da página.
        max_chars: Tamanho máximo de cada chunk em caracteres.

    Returns:
        Lista de strings (chunks).
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 para o espaço
        if current_len + line_len > max_chars and current:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if len(c) >= CHUNK_MIN_CHARS]


def _deduplicate(rules: list[RuleCandidate]) -> list[RuleCandidate]:
    """
    Remove regras duplicadas com base nos campos de identificação.

    Considera duplicata quando network, rule_type, card_family, product,
    merchant_group, channel, installment_band E rate_pct são iguais.

    Mantém a regra com maior confidence_score em caso de duplicata.
    """
    seen: dict[tuple, RuleCandidate] = {}

    for rule in rules:
        key = (
            rule.network,
            rule.region,
            rule.rule_type,
            rule.audience or "",
            rule.card_family or "",
            rule.product or "",
            rule.merchant_group or "",
            rule.channel or "",
            rule.installment_band or "",
            round(rule.rate_pct or 0.0, 4),
            round(rule.fixed_fee_amount or 0.0, 4),
        )
        if key not in seen or rule.confidence_score > seen[key].confidence_score:
            seen[key] = rule

    original_count = len(rules)
    deduplicated = list(seen.values())
    if original_count != len(deduplicated):
        logger.info(
            "Deduplicação: %d → %d regras (%d removidas)",
            original_count, len(deduplicated), original_count - len(deduplicated),
        )
    return deduplicated


def extract_from_document(
    path: str | Path,
    network: str,
    region: str = "BR",
    use_llm: bool = False,
) -> ExtractResult:
    """
    Extrai regras de intercâmbio de um documento (PDF ou texto).

    Este é o ponto de entrada principal do pipeline.

    Args:
        path:    Caminho para o arquivo (PDF, TXT, HTML).
        network: Bandeira ("Visa", "Mastercard", "AmericanExpress", "Elo", "Hipercard").
        region:  Região (padrão "BR").
        use_llm: Se True, usa LLM para normalização adicional.

    Returns:
        ExtractResult com todas as regras extraídas e metadados.
    """
    path = Path(path)
    logger.info("Iniciando pipeline: %s | network=%s | llm=%s", path.name, network, use_llm)

    if network not in SUPPORTED_NETWORKS:
        logger.warning(
            "Rede '%s' não está na lista de suportadas %s. Prosseguindo mesmo assim.",
            network, SUPPORTED_NETWORKS,
        )

    # 1. Ingestão
    pages = extract_text_pages(path)
    logger.info("Páginas/blocos extraídos: %d", len(pages))

    rules: list[RuleCandidate] = []
    warnings: list[str] = []

    # 2. Processamento por página
    for page_idx, page_text in enumerate(pages, start=1):
        if not page_text.strip():
            continue

        chunks = chunk_page_text(page_text)

        for chunk in chunks:
            # 3. Extração via regex
            regex_rules = normalize_snippet(
                chunk, network=network, region=region, page_number=page_idx
            )
            rules.extend(regex_rules)

            # 4. Extração via LLM (se habilitado)
            if use_llm:
                llm_rules_raw = normalize_with_llm(chunk)
                for row in llm_rules_raw:
                    row.setdefault("network", network)
                    row.setdefault("region", region)
                    row.setdefault("page_number", page_idx)
                    row.setdefault("evidence_text", chunk[:300])
                    row.setdefault("rule_type", "base_rate")
                    try:
                        candidate = RuleCandidate(**row)
                        validated = validate_rule(candidate)
                        rules.append(validated)
                    except Exception as e:
                        logger.debug("LLM retornou regra inválida: %s | %s", e, row)

    # 5. Deduplicação
    rules = _deduplicate(rules)

    # 6. Avisos
    if not rules:
        msg = (
            f"Nenhuma regra identificada em '{path.name}'. "
            "O arquivo pode ser escaneado (requer OCR), estar vazio, "
            "ou não conter padrões de intercâmbio reconhecíveis."
        )
        warnings.append(msg)
        logger.warning(msg)

    low_conf = [r for r in rules if r.confidence_score < 0.50]
    if low_conf:
        warnings.append(
            f"{len(low_conf)} regras com baixo score de confiança (<0.50). "
            "Recomenda-se revisão humana antes de usar em produção."
        )

    logger.info(
        "Pipeline concluído: %d regras extraídas (%d alta confiança, %d baixa)",
        len(rules),
        len([r for r in rules if r.confidence_score >= 0.70]),
        len(low_conf),
    )

    return ExtractResult(
        source_path=str(path),
        network=network,
        region=region,
        rules=rules,
        warnings=warnings,
    )


# Alias para compatibilidade com versão anterior
extract_from_pdf = extract_from_document


def main() -> None:
    """Ponto de entrada da CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Pipeline de extração de regras de intercâmbio das Bandeiras.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python -m src.pipeline --input data/visa_sample.txt --network Visa
  python -m src.pipeline --input manual_mc.pdf --network Mastercard --save
  python -m src.pipeline --input manual.pdf --network Visa --use-llm --save
        """,
    )
    parser.add_argument("--input", required=True, help="Caminho para o arquivo PDF ou TXT")
    parser.add_argument(
        "--network",
        required=True,
        choices=SUPPORTED_NETWORKS,
        help=f"Bandeira: {', '.join(SUPPORTED_NETWORKS)}",
    )
    parser.add_argument("--region", default="BR", help="Região (padrão: BR)")
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Habilitar normalização LLM via Anthropic Claude (requer ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Salvar regras no banco de dados",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Score mínimo de confiança para incluir no output (0.0–1.0)",
    )
    args = parser.parse_args()

    result = extract_from_document(
        args.input,
        network=args.network,
        region=args.region,
        use_llm=args.use_llm,
    )

    # Filtra por confiança mínima se especificado
    if args.min_confidence > 0:
        result = ExtractResult(
            source_path=result.source_path,
            network=result.network,
            region=result.region,
            rules=[r for r in result.rules if r.confidence_score >= args.min_confidence],
            warnings=result.warnings,
        )

    # Exibe resultado
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))

    if result.warnings:
        for w in result.warnings:
            print(f"\n⚠️  {w}")

    if args.save:
        from .database import init_db
        from .repository import save_rules

        init_db()
        count = save_rules(result.rules)
        print(f"\n✅ Regras salvas no banco: {count}")


if __name__ == "__main__":
    main()
