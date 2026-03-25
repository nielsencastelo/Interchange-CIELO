# 🏦 Interchange AI — Pipeline de IA para Taxas de Intercâmbio

> **Desafio: Bolsista Doutor | PUCPR Digital**  
> Desenvolvimento de pipeline de IA para extração e estruturação automática das regras  
> de taxas de intercâmbio dos manuais das Bandeiras (Visa e Mastercard).

---

## 📌 Visão Geral

Este projeto implementa um **pipeline completo de Inteligência Artificial** para:

1. **Ingerir** documentos técnicos das Bandeiras (PDF, HTML, CSV)
2. **Extrair** regras de intercâmbio via regex + LLM (Anthropic Claude)
3. **Validar e normalizar** as regras extraídas com score de confiança
4. **Persistir** em banco de dados relacional (SQLite/PostgreSQL)
5. **Expor** via API REST (FastAPI) para consultas e simulações
6. **Visualizar** comparativos entre Bandeiras via Dashboard (Streamlit)
7. **Gerar relatórios** PDF/HTML com análise exploratória
8. **Orquestrar** via DAG Airflow (opcional)

---

## Lindk extração dos dados
- https://developercielo.github.io/
- https://www.visa.com/en-us/support/visa-rules

## 🗂️ Estrutura do Projeto

```
interchange_ai/
├── src/
│   ├── extract/
│   │   ├── pdf_reader.py          # Leitura de PDFs (pdfplumber + pypdf)
│   │   ├── html_reader.py         # Leitura de páginas HTML das Bandeiras
│   │   ├── patterns.py            # Regex para percentuais, caps, bandas
│   │   └── llm_normalizer.py      # Normalização via Anthropic Claude API
│   ├── api/
│   │   └── main.py                # FastAPI: endpoints REST
│   ├── reports/
│   │   └── generator.py           # Gerador de relatório HTML/PDF
│   ├── config.py                  # Configurações via .env
│   ├── schemas.py                 # Pydantic models
│   ├── database.py                # SQLAlchemy ORM
│   ├── normalizer.py              # Inferência de campos (produto, canal, etc.)
│   ├── validator.py               # Validação + score de confiança
│   ├── repository.py              # CRUD no banco de dados
│   ├── simulator.py               # Motor de simulação de taxas
│   ├── pipeline.py                # Orquestrador principal do pipeline
│   ├── seed_sample_data.py        # Carga de dados de amostra no DB
│   └── dashboard.py               # Streamlit dashboard
├── data/
│   ├── sample_interchange_rules.csv   # Dados reais de amostra (Visa + Mastercard BR)
│   ├── visa_sample.txt                # Trechos reais de manual Visa
│   └── mastercard_sample.txt          # Trechos reais de manual Mastercard
├── sql/
│   └── 001_schema.sql             # Schema PostgreSQL com índices e versioning
├── tests/
│   ├── test_patterns.py           # Testes unitários de regex
│   ├── test_normalizer.py         # Testes do normalizador
│   ├── test_validator.py          # Testes do validador
│   ├── test_simulator.py          # Testes do simulador
│   └── test_pipeline.py           # Testes de integração do pipeline
├── notebooks/
│   └── exploratory_analysis.py    # Análise exploratória (pode ser ipynb)
├── airflow/
│   └── dag_interchange.py         # DAG Airflow (opcional)
├── docs/
│   └── architecture.md            # Documentação de arquitetura
├── .env.example                   # Variáveis de ambiente
├── docker-compose.yml             # PostgreSQL + Airflow local
├── requirements.txt               # Dependências Python
└── README.md                      # Este arquivo
```

---

## ⚙️ Pré-requisitos

| Requisito | Versão mínima | Obs |
|-----------|--------------|-----|
| Python    | 3.10+        | 3.12 recomendado |
| pip       | 23+          | — |
| Docker    | 24+ (opcional) | Para PostgreSQL local |
| Git       | 2.40+        | — |

---

## 🚀 Instalação Passo a Passo

### 1. Clonar / extrair o projeto

```bash
# Se baixou o ZIP:
unzip interchange_ai.zip -d interchange_ai
cd interchange_ai

# Se for repositório git:
git clone <url> interchange_ai
cd interchange_ai
```

### 2. Criar e ativar ambiente virtual

```bash
# Criar
python -m venv .venv

# Ativar no Linux/macOS
source .venv/bin/activate

# Ativar no Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Ativar no Windows (CMD)
.venv\Scripts\activate.bat
```

### 3. Instalar dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

```bash
# Copiar template
cp .env.example .env

# Editar com seu editor preferido
nano .env   # ou code .env / vim .env
```

Variáveis importantes no `.env`:

```dotenv
# Banco de dados (padrão: SQLite local, sem Docker)
DATABASE_URL=sqlite+pysqlite:///./interchange_ai.db

# Para PostgreSQL (requer Docker ou instância externa):
# DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/interchange_ai

# Anthropic Claude API (necessário para normalização LLM)
ANTHROPIC_API_KEY=sk-ant-...
ENABLE_LLM_NORMALIZATION=true

# Modelo Anthropic a usar
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

> 💡 **Sem API Key:** O pipeline funciona 100% sem chave Anthropic, usando apenas  
> extração por regex. A normalização LLM é um enriquecimento opcional.

---

## 🛢️ Banco de Dados

### Opção A — SQLite (sem Docker, zero configuração)

Deixe o padrão no `.env`:
```dotenv
DATABASE_URL=sqlite+pysqlite:///./interchange_ai.db
```
O arquivo `interchange_ai.db` será criado automaticamente na raiz do projeto.

### Opção B — PostgreSQL via Docker

```bash
# Subir o banco
docker compose up -d db

# Aguardar ~5s e verificar
docker compose logs db | tail -5

# Criar as tabelas com o schema completo
psql postgresql://postgres:postgres@localhost:5432/interchange_ai -f sql/001_schema.sql
```

---

## 📦 Carga dos Dados de Amostra

```bash
# Carrega sample_interchange_rules.csv no banco
python -m src.seed_sample_data
```

Saída esperada:
```
Iniciando carga de dados de amostra...
Regras Visa carregadas: 24
Regras Mastercard carregadas: 22
Total de regras carregadas: 46
```

---

## 🔄 Executar o Pipeline de Extração

### Extrair de um PDF das Bandeiras

```bash
# Extrair e exibir resultado JSON
python -m src.pipeline --input caminho/para/manual_visa.pdf --network Visa --region BR

# Extrair e salvar no banco de dados
python -m src.pipeline --input caminho/para/manual_visa.pdf --network Visa --region BR --save

# Extrair com normalização LLM (requer ANTHROPIC_API_KEY no .env)
python -m src.pipeline --input manual.pdf --network Mastercard --region BR --save --use-llm
```

### Extrair de texto de amostra incluído

```bash
# Usando os arquivos de texto incluídos no projeto
python -m src.pipeline --input data/visa_sample.txt --network Visa --region BR --save
python -m src.pipeline --input data/mastercard_sample.txt --network Mastercard --region BR --save
```

---

## 🌐 API REST (FastAPI)

### Iniciar o servidor

```bash
uvicorn src.api.main:app --reload --port 8000
```

### Endpoints disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| GET    | `/health` | Health check |
| GET    | `/rules` | Listar todas as regras |
| GET    | `/rules/filter` | Filtrar regras por parâmetros |
| POST   | `/simulate` | Simular taxa para uma transação |
| POST   | `/extract` | Upload de PDF para extração |
| GET    | `/compare` | Comparativo Visa vs Mastercard |
| GET    | `/stats` | Estatísticas da base |
| GET    | `/docs` | Swagger UI interativo |

### Exemplos de uso

```bash
# Listar todas as regras
curl http://localhost:8000/rules

# Filtrar por bandeira e família de cartão
curl "http://localhost:8000/rules/filter?network=Visa&card_family=credit"

# Simular taxa
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "network": "Visa",
    "region": "BR",
    "audience": "PF",
    "card_family": "credit",
    "product": "Platinum",
    "merchant_group": "supermercados",
    "channel": "cp",
    "installment_band": null
  }'

# Upload de PDF
curl -X POST http://localhost:8000/extract \
  -F "file=@manual_visa.pdf" \
  -F "network=Visa" \
  -F "region=BR"
```

### Documentação interativa

Acesse: **http://localhost:8000/docs** (Swagger UI)

---

## 📊 Dashboard Streamlit

```bash
streamlit run src/dashboard.py
```

Acesse: **http://localhost:8501**

O dashboard apresenta:
- 📋 Tabela consolidada de todas as regras
- 📊 Gráficos comparativos Visa × Mastercard
- 🔍 Filtros interativos por bandeira, família, produto, segmento
- 💹 Boxplot de dispersão de taxas por produto
- 🔄 Simulador de taxa interativo
- 📤 Export CSV das regras filtradas

---

## 🧪 Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ -v --cov=src --cov-report=term-missing

# Teste específico
pytest tests/test_patterns.py -v
```

---

## 📄 Gerar Relatório de Análise

```bash
python -m src.reports.generator
```

Gera `relatorio_intercambio.html` na raiz do projeto com:
- Análise exploratória completa
- Tabelas comparativas Visa × Mastercard
- Gráficos de distribuição
- Recomendações técnicas

---

## 🔁 Airflow DAG (Orquestração)

```bash
# Requer Airflow instalado e configurado
export AIRFLOW_HOME=./airflow
airflow db init
airflow dags list

# Triggerar DAG manualmente
airflow dags trigger interchange_pipeline
```

---

## 🏗️ Arquitetura do Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                    FONTES DE DADOS                       │
│  PDF (Visa/MC)  │  HTML (sites)  │  CSV (estruturado)   │
└────────┬────────┴───────┬────────┴──────────┬───────────┘
         │                │                   │
         ▼                ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                  CAMADA DE INGESTÃO                      │
│   pdf_reader.py  │  html_reader.py  │  csv_loader.py    │
└─────────────────────────┬───────────────────────────────┘
                          │  texto bruto por página/chunk
                          ▼
┌─────────────────────────────────────────────────────────┐
│               CAMADA DE EXTRAÇÃO                         │
│                                                          │
│   ┌─────────────────┐    ┌──────────────────────────┐  │
│   │  patterns.py    │    │   llm_normalizer.py       │  │
│   │  (regex rules)  │    │   (Anthropic Claude API)  │  │
│   └────────┬────────┘    └────────────┬─────────────┘  │
│            └──────────┬───────────────┘                  │
└───────────────────────┼─────────────────────────────────┘
                        │  RuleCandidate (raw)
                        ▼
┌─────────────────────────────────────────────────────────┐
│           CAMADA DE NORMALIZAÇÃO + VALIDAÇÃO             │
│   normalizer.py → inferência de campos                   │
│   validator.py  → score de confiança (0.0 - 1.0)         │
└─────────────────────────┬───────────────────────────────┘
                          │  RuleCandidate (validado)
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  CAMADA DE PERSISTÊNCIA                  │
│   repository.py → SQLAlchemy → SQLite / PostgreSQL       │
│   sql/001_schema.sql → schema completo com versioning    │
└─────────────────────────┬───────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
┌─────────────────────┐  ┌─────────────────────────────┐
│   API REST          │  │   Dashboard Streamlit        │
│   FastAPI           │  │   Comparativos + Simulador   │
│   /rules /simulate  │  │   streamlit run dashboard.py │
└─────────────────────┘  └─────────────────────────────┘
```

---

## 🧠 Uso da LLM (Anthropic Claude)

O módulo `src/extract/llm_normalizer.py` usa a API da Anthropic para normalizar  
trechos ambíguos dos manuais das Bandeiras que os regex não conseguem capturar.

**Quando ativar:** Documentos complexos com tabelas aninhadas, notas de rodapé,  
condicionais implícitas ou linguagem técnica não padronizada.

**Configuração:**
```dotenv
ANTHROPIC_API_KEY=sk-ant-...
ENABLE_LLM_NORMALIZATION=true
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

**Custo estimado:** ~R$ 0,05–0,15 por página de manual processada com Claude Sonnet.

---

## 📚 Referências

- [Visa Brazil Interchange Reimbursement Fees](https://usa.visa.com/support/consumer/visa-rules.html)
- [Mastercard Interchange Rates & Fees](https://www.mastercard.com/gateway/solutions/payment-solutions/interchange.html)
- [Cielo Manual de Taxas de Intercâmbio](https://developercielo.github.io/)
- [Banco Central do Brasil — Regulamentação de Arranjos de Pagamento](https://www.bcb.gov.br/estabilidadefinanceira/arranjos_pagamento)
- [pdfplumber — Documentação](https://github.com/jsvine/pdfplumber)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 📝 Licença

Projeto desenvolvido para o **Desafio Bolsista Doutor — PUCPR Digital**.  
Uso acadêmico e de pesquisa.

---

*Gerado em 2026 — Roberto Braga Jr. / NCDD*
