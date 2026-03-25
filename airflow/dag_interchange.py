"""
airflow/dag_interchange.py
==========================
DAG Airflow para orquestração automática do pipeline de intercâmbio.

Executa semanalmente:
    1. Verifica novos manuais em s3 / pasta local
    2. Extrai regras (regex + LLM opcional)
    3. Valida e persiste no banco
    4. Gera relatório HTML
    5. Notifica via e-mail / Slack se houver mudanças

Instalação do Airflow (ambiente isolado recomendado):
    pip install apache-airflow==2.9.3
    export AIRFLOW_HOME=./airflow_home
    airflow db migrate
    airflow users create --username admin --password admin \
        --firstname Admin --lastname Admin --role Admin --email admin@local.com
    airflow webserver --port 8080 &
    airflow scheduler &

Depois copie este arquivo para:
    $AIRFLOW_HOME/dags/dag_interchange.py

Acesse: http://localhost:8080
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Guard: o Airflow pode não estar instalado em todos os ambientes
# ---------------------------------------------------------------------------
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.operators.email import EmailOperator
    from airflow.utils.dates import days_ago
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    # Stub para que o módulo possa ser importado sem Airflow
    class DAG:  # type: ignore
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
    class PythonOperator:  # type: ignore
        def __init__(self, *a, **kw): pass
    def days_ago(n): return datetime.now()  # type: ignore

import logging
import os
import sys

# Garante que o projeto está no PYTHONPATH quando rodando via Airflow
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

DEFAULT_ARGS = {
    "owner": "interchange-ai",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": days_ago(1),
}

# Pasta onde novos PDFs das Bandeiras são depositados
INBOX_DIR = os.environ.get(
    "INTERCHANGE_INBOX_DIR",
    str(PROJECT_ROOT / "data" / "inbox"),
)

# Pasta de arquivos já processados
PROCESSED_DIR = os.environ.get(
    "INTERCHANGE_PROCESSED_DIR",
    str(PROJECT_ROOT / "data" / "processed"),
)


# ---------------------------------------------------------------------------
# Funções das tasks
# ---------------------------------------------------------------------------

def task_check_inbox(**context) -> dict:
    """
    Task 1: Verifica pasta de entrada por novos PDFs.

    Retorna dict com lista de arquivos a processar via XCom.
    """
    inbox = Path(INBOX_DIR)
    inbox.mkdir(parents=True, exist_ok=True)

    pdfs = list(inbox.glob("*.pdf")) + list(inbox.glob("*.txt"))
    logger.info("Inbox: %d arquivos encontrados em %s", len(pdfs), inbox)

    files_info = []
    for f in pdfs:
        # Infere rede pelo nome do arquivo
        name_lower = f.name.lower()
        if "visa" in name_lower:
            network = "Visa"
        elif "mastercard" in name_lower or "mc" in name_lower:
            network = "Mastercard"
        elif "amex" in name_lower or "american" in name_lower:
            network = "AmericanExpress"
        elif "elo" in name_lower:
            network = "Elo"
        elif "hipercard" in name_lower:
            network = "Hipercard"
        else:
            network = "Visa"  # padrão
        files_info.append({"path": str(f), "network": network})

    context["ti"].xcom_push(key="files_to_process", value=files_info)
    logger.info("Arquivos a processar: %s", files_info)
    return {"count": len(files_info), "files": [f["path"] for f in files_info]}


def task_extract_rules(**context) -> dict:
    """
    Task 2: Executa o pipeline de extração para cada arquivo.

    Lê a lista de arquivos do XCom da task anterior.
    """
    from src.database import init_db
    from src.pipeline import extract_from_document
    from src.repository import save_extraction_log, save_rules

    init_db()

    files_info = context["ti"].xcom_pull(
        task_ids="check_inbox", key="files_to_process"
    ) or []

    if not files_info:
        logger.info("Nenhum arquivo para processar.")
        return {"total_rules": 0, "files_processed": 0}

    use_llm = os.environ.get("ENABLE_LLM_NORMALIZATION", "false").lower() == "true"
    total_saved = 0
    files_processed = 0

    for file_info in files_info:
        path = file_info["path"]
        network = file_info["network"]

        if not Path(path).exists():
            logger.warning("Arquivo não encontrado: %s", path)
            continue

        logger.info("Extraindo: %s | network=%s | llm=%s", path, network, use_llm)

        try:
            result = extract_from_document(path, network=network, use_llm=use_llm)
            saved = save_rules(result.rules, version_tag=f"airflow-{datetime.now().strftime('%Y%m%d')}")

            high = len([r for r in result.rules if r.confidence_score >= 0.70])
            low = len([r for r in result.rules if r.confidence_score < 0.50])

            save_extraction_log(
                source_path=path,
                network=network,
                region="BR",
                total_rules=len(result.rules),
                high_confidence=high,
                low_confidence=low,
                warnings=result.warnings,
                status="success",
            )

            total_saved += saved
            files_processed += 1
            logger.info("Extraídas %d regras de %s (%d alta conf.)", saved, path, high)

            # Move para processados
            processed = Path(PROCESSED_DIR)
            processed.mkdir(parents=True, exist_ok=True)
            Path(path).rename(processed / Path(path).name)

        except Exception as exc:
            logger.error("Erro ao processar %s: %s", path, exc)
            save_extraction_log(
                source_path=path, network=network, region="BR",
                total_rules=0, high_confidence=0, low_confidence=0,
                warnings=[str(exc)], status="error",
            )

    context["ti"].xcom_push(key="total_rules_extracted", value=total_saved)
    return {"total_rules": total_saved, "files_processed": files_processed}


def task_generate_report(**context) -> str:
    """Task 3: Gera relatório HTML atualizado."""
    from src.reports.generator import generate_report

    output = str(PROJECT_ROOT / "relatorio_intercambio.html")
    generate_report(output_path=output)
    logger.info("Relatório gerado: %s", output)
    return output


def task_validate_bcb_compliance(**context) -> dict:
    """
    Task 4: Valida aderência às regras do BCB.

    Verifica se taxas de débito e pré-pago estão dentro dos tetos regulatórios.
    Gera alerta se houver não-conformidade.
    """
    from src.repository import list_rules

    # Limites BCB (Resolução BCB nº 35/2020)
    BCB_DEBIT_MAX_PCT = 0.50
    BCB_DEBIT_CAP_BRL = 0.35
    BCB_PREPAID_MAX_PCT = 0.70

    violations = []

    debit_rules = list_rules(card_family="debit", rule_type="base_rate")
    for rule in debit_rules:
        if rule.rate_pct and rule.network != "BCB_Limite":
            if rule.rate_pct > BCB_DEBIT_MAX_PCT:
                violations.append(
                    f"DÉBITO ACIMA DO TETO BCB: {rule.network} {rule.product} "
                    f"{rule.rate_pct:.2f}% > {BCB_DEBIT_MAX_PCT:.2f}%"
                )

    prepaid_rules = list_rules(card_family="prepaid", rule_type="base_rate")
    for rule in prepaid_rules:
        if rule.rate_pct and rule.network != "BCB_Limite":
            if rule.rate_pct > BCB_PREPAID_MAX_PCT:
                violations.append(
                    f"PRÉ-PAGO ACIMA DO TETO BCB: {rule.network} {rule.product} "
                    f"{rule.rate_pct:.2f}% > {BCB_PREPAID_MAX_PCT:.2f}%"
                )

    if violations:
        logger.warning("⚠️  %d violações BCB detectadas:", len(violations))
        for v in violations:
            logger.warning("  %s", v)
    else:
        logger.info("✅ Todas as regras estão dentro dos limites BCB.")

    context["ti"].xcom_push(key="bcb_violations", value=violations)
    return {"violations": violations, "count": len(violations)}


def task_seed_if_empty(**context) -> str:
    """Task 0 (opcional): Carrega dados de amostra se o banco estiver vazio."""
    from src.database import init_db
    from src.repository import count_rules

    init_db()
    if count_rules() == 0:
        logger.info("Banco vazio. Carregando dados de amostra...")
        from src.seed_sample_data import main as seed_main
        seed_main(reset=False)
        return "seeded"
    return "already_populated"


# ---------------------------------------------------------------------------
# Definição do DAG
# ---------------------------------------------------------------------------

with DAG(
    dag_id="interchange_pipeline",
    description=(
        "Pipeline de extração automática de regras de intercâmbio "
        "— Visa, Mastercard, Amex, Elo, Hipercard, BCB"
    ),
    schedule_interval="0 6 * * 1",  # Toda segunda-feira às 06:00 BRT
    default_args=DEFAULT_ARGS,
    catchup=False,
    max_active_runs=1,
    tags=["interchange", "fintech", "bandeiras", "pucpr"],
    doc_md="""
## Interchange AI Pipeline DAG

Orquestra o pipeline semanal de extração e análise de taxas de intercâmbio.

### Fluxo
1. **seed_if_empty** — Carrega amostra se banco vazio
2. **check_inbox** — Verifica novos PDFs em `data/inbox/`
3. **extract_rules** — Extrai e persiste regras (regex + LLM opcional)
4. **generate_report** — Atualiza relatório HTML
5. **validate_bcb** — Verifica conformidade com BCB

### Variáveis de ambiente
- `INTERCHANGE_INBOX_DIR` — Pasta de entrada de PDFs
- `ENABLE_LLM_NORMALIZATION` — true/false para ativar LLM
""",
) as dag:

    seed_task = PythonOperator(
        task_id="seed_if_empty",
        python_callable=task_seed_if_empty,
        doc_md="Carrega dados de amostra se o banco estiver vazio.",
    )

    check_task = PythonOperator(
        task_id="check_inbox",
        python_callable=task_check_inbox,
        doc_md="Verifica pasta data/inbox/ por novos PDFs das Bandeiras.",
    )

    extract_task = PythonOperator(
        task_id="extract_rules",
        python_callable=task_extract_rules,
        doc_md="Executa pipeline de extração (regex + LLM) para cada arquivo.",
    )

    report_task = PythonOperator(
        task_id="generate_report",
        python_callable=task_generate_report,
        doc_md="Gera relatório HTML com análise exploratória atualizada.",
    )

    bcb_task = PythonOperator(
        task_id="validate_bcb_compliance",
        python_callable=task_validate_bcb_compliance,
        doc_md="Valida conformidade com tetos regulatórios do Banco Central.",
    )

    # Ordem de execução
    seed_task >> check_task >> extract_task >> [report_task, bcb_task]
