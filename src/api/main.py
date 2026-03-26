"""
src/api/main.py
===============
API REST para consulta, simulação e extração de regras de intercâmbio.

Endpoints:
    GET  /health            — Health check
    GET  /rules             — Listar todas as regras
    GET  /rules/filter      — Filtrar regras por parâmetros
    POST /simulate          — Simular taxa para uma transação
    POST /compare           — Comparar taxas entre Bandeiras
    POST /extract           — Upload de PDF para extração
    GET  /stats             — Estatísticas da base
    GET  /docs              — Swagger UI interativo

Uso:
    uvicorn src.api.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..database import init_db
from ..pipeline import SUPPORTED_NETWORKS, extract_from_document
from ..repository import count_rules, delete_all, get_all_rules, get_stats, list_rules, save_rules
from ..schemas import RuleCandidate, SimulationRequest, SimulationResponse, UploadResponse
from ..simulator import compare_networks, simulate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Aplicação FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Interchange AI API",
    description=(
        "Pipeline de IA para extração e consulta de taxas de intercâmbio "
        "das Bandeiras (Visa, Mastercard (Opcional: Amex, Elo, Hipercard) — Brasil.\n\n"
        "**Desafio Bolsista**"
    ),
    version="2.0.0",

    license_info={"name": "Acadêmico / Pesquisa"},
)

# CORS — permite acesso do dashboard Streamlit e de clientes externos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Eventos de ciclo de vida
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup() -> None:
    """Inicializa o banco de dados na startup da aplicação."""
    init_db()
    total = count_rules()
    logger.info("API iniciada. Regras no banco: %d", total)
    if total == 0:
        logger.warning(
            "Banco vazio! Execute: python -m src.seed_sample_data"
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Sistema"])
def health() -> dict[str, str]:
    """Verifica se a API está respondendo."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/stats", tags=["Sistema"])
def stats() -> dict[str, Any]:
    """
    Retorna estatísticas agregadas da base de regras.

    Inclui:
    - Total de regras por bandeira
    - Distribuição por tipo de regra e família de cartão
    - Score médio de confiança
    """
    return get_stats()


@app.get("/rules", tags=["Regras"], response_model=list[dict])
def get_rules(limit: int = Query(default=500, le=2000)) -> list[dict]:
    """Lista todas as regras do banco (sem filtros)."""
    rules = list_rules(limit=limit)
    return [r.model_dump(mode="json") for r in rules]


@app.get("/rules/filter", tags=["Regras"])
def filter_rules(
    network: str | None = Query(default=None, description="Bandeira: Visa, Mastercard, AmericanExpress, Elo, Hipercard"),
    card_family: str | None = Query(default=None, description="Família: credit, debit, prepaid, cash_withdrawal"),
    rule_type: str | None = Query(default=None, description="Tipo: base_rate, merchant_adjustment, ..."),
    audience: str | None = Query(default=None, description="Público: PF, PJ, ALL"),
    product: str | None = Query(default=None, description="Produto: Classic, Gold, Platinum, ..."),
    merchant_group: str | None = Query(default=None, description="Segmento: supermercados, outros, ..."),
    channel: str | None = Query(default=None, description="Canal: cp, cnp, atm, cp_contactless"),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, description="Score mínimo de confiança"),
    limit: int = Query(default=200, le=1000),
) -> list[dict]:
    """
    Filtra regras por múltiplos parâmetros.

    Todos os parâmetros são opcionais (AND lógico entre eles).
    """
    rules = list_rules(
        network=network,
        card_family=card_family,
        rule_type=rule_type,
        audience=audience,
        product=product,
        merchant_group=merchant_group,
        channel=channel,
        min_confidence=min_confidence,
        limit=limit,
    )
    return [r.model_dump(mode="json") for r in rules]


@app.post("/simulate", tags=["Simulação"], response_model=dict)
def post_simulate(request: SimulationRequest) -> dict:
    """
    Simula a taxa de intercâmbio para uma transação.

    Retorna:
    - Taxa efetiva (percentual)
    - Taxa fixa (BRL, se houver)
    - Cap aplicado (se houver)
    - Fee estimado em BRL (se transaction_amount informado)
    - Regras utilizadas no cálculo
    - Notas explicativas

    Exemplo de body:
    ```json
    {
      "network": "Visa",
      "region": "BR",
      "audience": "PF",
      "card_family": "credit",
      "product": "Platinum",
      "merchant_group": "supermercados",
      "channel": "cp",
      "installment_band": null,
      "transaction_amount": 500.00
    }
    ```
    """
    all_rules = get_all_rules()
    result = simulate(all_rules, request)
    return result.model_dump(mode="json")


@app.post("/compare", tags=["Simulação"])
def post_compare(
    request: SimulationRequest,
    networks: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compara taxas de intercâmbio entre múltiplas Bandeiras.

    Executa a mesma simulação para cada Bandeira e retorna os resultados
    lado a lado para facilitar análise comparativa.

    Query param `networks` (opcional): lista de bandeiras a comparar.
    Se omitido, compara todas as bandeiras disponíveis no banco.
    """
    all_rules = get_all_rules()
    results = compare_networks(all_rules, request, networks=networks)
    return {
        net: resp.model_dump(mode="json")
        for net, resp in results.items()
    }


@app.post("/extract", tags=["Pipeline"], response_model=UploadResponse)
async def extract(
    file: UploadFile = File(..., description="PDF ou TXT a processar"),
    network: str = Query(default="Visa", description=f"Bandeira: {', '.join(SUPPORTED_NETWORKS)}"),
    region: str = Query(default="BR"),
    use_llm: bool = Query(default=False, description="Usar LLM para normalização adicional"),
    save: bool = Query(default=True, description="Salvar regras extraídas no banco"),
) -> UploadResponse:
    """
    Faz upload de um PDF das Bandeiras e executa o pipeline de extração.

    1. Recebe o arquivo
    2. Salva temporariamente em disco
    3. Executa o pipeline de extração (regex + LLM opcional)
    4. Persiste as regras no banco (se save=true)
    5. Retorna estatísticas da extração

    Formatos aceitos: PDF, TXT
    """
    if network not in SUPPORTED_NETWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Bandeira '{network}' não suportada. Use: {SUPPORTED_NETWORKS}",
        )

    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = extract_from_document(
            tmp_path,
            network=network,
            region=region,
            use_llm=use_llm,
        )
    except Exception as e:
        logger.error("Erro na extração: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro na extração: {e}")

    saved_count = 0
    if save and result.rules:
        saved_count = save_rules(result.rules)

    high_conf = len([r for r in result.rules if r.confidence_score >= 0.70])
    low_conf = len([r for r in result.rules if r.confidence_score < 0.50])

    return UploadResponse(
        message=f"Extração concluída para {network}",
        extracted_rules=len(result.rules),
        high_confidence=high_conf,
        low_confidence=low_conf,
        warnings=result.warnings,
    )


@app.delete("/rules", tags=["Admin"])
def delete_rules(
    network: str | None = Query(default=None, description="Bandeira específica (vazio = todas)"),
    confirm: bool = Query(default=False, description="Confirmar deleção (obrigatório: true)"),
) -> dict[str, int]:
    """
    Remove regras do banco (operação destrutiva — use com cuidado).

    Requer `confirm=true` para prevenir deleção acidental.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Passe confirm=true para confirmar a deleção.",
        )
    count = delete_all(network=network)
    return {"deleted": count}


@app.get("/networks", tags=["Referência"])
def get_networks() -> list[str]:
    """Retorna a lista de bandeiras suportadas pelo pipeline."""
    return SUPPORTED_NETWORKS


@app.get("/rule-types", tags=["Referência"])
def get_rule_types() -> list[str]:
    """Retorna os tipos de regra suportados pelo schema."""
    from ..schemas import RULE_TYPES
    return RULE_TYPES
