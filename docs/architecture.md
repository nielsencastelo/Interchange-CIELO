# Interchange AI — Documentação de Arquitetura

## Visão Geral

O **Interchange AI** é um pipeline de Inteligência Artificial para extração,
estruturação e análise automática de regras de taxas de intercâmbio dos manuais
das Bandeiras de cartões de pagamento (Visa, Mastercard, American Express, Elo,
Hipercard) operantes no Brasil, com conformidade regulatória ao Banco Central do Brasil.

---

## Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FONTES DE DADOS                             │
│                                                                     │
│  PDF Nativo    PDF Escaneado    HTML (sites)    CSV Estruturado     │
│  (Visa/MC)     (OCR needed)    (Cielo/Amex)    (dados validados)   │
└────────┬───────────────┬──────────────┬────────────────┬───────────┘
         │               │              │                │
         ▼               ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CAMADA DE INGESTÃO                               │
│                                                                     │
│   pdf_reader.py      pdf_reader.py    html_reader.py   pandas CSV  │
│   (pdfplumber)       (pytesseract)    (httpx+parser)               │
└─────────────────────────────┬───────────────────────────────────────┘
                              │  Texto bruto por página/chunk
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   CAMADA DE EXTRAÇÃO                                │
│                                                                     │
│   ┌─────────────────────────┐    ┌────────────────────────────┐    │
│   │  patterns.py (Regex)    │    │  llm_normalizer.py (LLM)   │    │
│   │                         │    │                            │    │
│   │  - Percentuais (%)      │    │  Provedores suportados:    │    │
│   │  - Valores BRL          │    │  • Anthropic Claude ✓      │    │
│   │  - Bandas parcelas      │    │  • OpenAI GPT ✓            │    │
│   │  - Caps/Floors          │    │  • Google Gemini ✓         │    │
│   │  - Termos de canal      │    │  • Ollama (local) ✓        │    │
│   └────────────┬────────────┘    └────────────┬───────────────┘    │
└────────────────┼─────────────────────────────┼────────────────────┘
                 └──────────────┬──────────────┘
                                │  RuleCandidate (raw)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              CAMADA DE NORMALIZAÇÃO + VALIDAÇÃO                     │
│                                                                     │
│   normalizer.py                                                     │
│   ├── infer_rule_type()    → base_rate | adjustment | fixed_fee    │
│   ├── infer_card_family()  → credit | debit | prepaid              │
│   ├── infer_product()      → Classic | Gold | Platinum | Black...  │
│   ├── infer_merchant_group() → supermercados | hoteis | outros     │
│   ├── infer_channel()      → cp | cnp | contactless | atm          │
│   └── infer_audience()     → PF | PJ | ALL                         │
│                                                                     │
│   validator.py                                                      │
│   ├── Validação de faixas de taxa por família (BCB-aware)          │
│   ├── Score de confiança [0.0 – 1.0]                               │
│   └── Alertas de revisão humana (score < 0.50)                     │
└─────────────────────────────┬───────────────────────────────────────┘
                              │  RuleCandidate (validado + scored)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   CAMADA DE PERSISTÊNCIA                            │
│                                                                     │
│   repository.py + database.py                                       │
│   ├── SQLAlchemy ORM                                                │
│   ├── SQLite (dev) / PostgreSQL 16 + pgvector (prod)               │
│   ├── Views analíticas (vw_base_rates, vw_network_stats, vw_bcb)   │
│   ├── Full-text search (pg_trgm)                                    │
│   ├── Versionamento por version_tag                                 │
│   └── ExtractionLog para auditoria                                  │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
┌─────────────────┐  ┌────────────────┐  ┌────────────────────────┐
│  API REST       │  │  Dashboard     │  │  Relatório HTML        │
│  FastAPI        │  │  Streamlit     │  │  reports/generator.py  │
│                 │  │  + Plotly      │  │                        │
│  /rules         │  │                │  │  - Análise exploratória│
│  /rules/filter  │  │  - Tabela      │  │  - Comparativo bandeiras│
│  /simulate      │  │  - Gráficos    │  │  - Análise BCB         │
│  /compare       │  │  - Simulador   │  │  - Pipeline proposto   │
│  /extract       │  │  - Export CSV  │  │  - Recomendações IA    │
│  /stats         │  │                │  │                        │
│  /docs (Swagger)│  │  :8501         │  │  relatorio.html        │
│  :8000          │  │                │  │                        │
└─────────────────┘  └────────────────┘  └────────────────────────┘

            ┌─────────────────────────────────────┐
            ▼                                     │
┌───────────────────────┐                         │
│  Airflow DAG          │   (orquestração semanal) │
│                       │◄────────────────────────┘
│  seed_if_empty        │
│  → check_inbox        │
│  → extract_rules      │
│  → generate_report    │
│  → validate_bcb       │
└───────────────────────┘
```

---

## Módulos

| Módulo | Responsabilidade | Linhas aprox. |
|--------|-----------------|--------------|
| `src/extract/patterns.py` | Regex para percentuais, BRL, caps, bandas | 216 |
| `src/extract/pdf_reader.py` | Leitura PDF com pdfplumber/pypdf | 164 |
| `src/extract/html_reader.py` | Scraping de páginas HTML das Bandeiras | 130 |
| `src/extract/llm_normalizer.py` | Normalização LLM multi-provedor | 202 |
| `src/normalizer.py` | Inferência de campos (produto, canal, segmento) | 329 |
| `src/validator.py` | Score de confiança + validação BCB-aware | 174 |
| `src/pipeline.py` | Orquestrador principal | 306 |
| `src/simulator.py` | Motor de simulação de taxa efetiva | 292 |
| `src/repository.py` | CRUD SQLAlchemy | 278 |
| `src/database.py` | ORM models + engine | 151 |
| `src/schemas.py` | Pydantic models | 167 |
| `src/config.py` | Configurações multi-LLM | 53 |
| `src/api/main.py` | FastAPI REST API | 285 |
| `src/dashboard.py` | Streamlit + Plotly | 457 |
| `src/reports/generator.py` | Relatório HTML standalone | 560 |
| `src/seed_sample_data.py` | Carga de dados de amostra | 161 |
| `airflow/dag_interchange.py` | DAG de orquestração | 220 |

---

## Decisões de Arquitetura

### Por que regex + LLM em camadas?

A abordagem híbrida garante que:
1. **Regex** captura 70-80% dos casos com custo zero e latência nula
2. **LLM** é acionada apenas para os 20-30% ambíguos, reduzindo custo de API
3. O **score de confiança** direciona revisão humana para casos duvidosos

Isso implementa o padrão **Human-in-the-Loop (HITL)** recomendado para domínios regulatórios.

### Por que multi-provedor LLM?

A abstração de provedor evita vendor lock-in e permite:
- **Produção**: Claude (melhor precisão para documentos técnicos em PT-BR)
- **Desenvolvimento**: Ollama local (zero custo, privacidade)
- **Alternativa**: OpenAI / Gemini para equipes com contratos existentes

### Por que SQLite para desenvolvimento?

- Zero configuração (sem Docker para começar)
- Mesmo código SQLAlchemy funciona em SQLite e PostgreSQL
- Migração trivial: trocar `DATABASE_URL` no `.env`

---

## Conformidade Regulatória BCB

O sistema valida automaticamente aderência à Resolução BCB nº 35/2020:

| Modalidade | Limite | Implementação |
|-----------|--------|--------------|
| Débito doméstico | máx 0,50% | `validator.py` RATE_RANGES |
| Débito baixo valor | teto R$ 0,35 | CSV BCB_Limite + view `vw_bcb_compliance` |
| Pré-pago doméstico | máx 0,70% | `validator.py` RATE_RANGES |
| Transporte público | teto R$ 0,12 | CSV BCB_Limite |

---

## Roadmap Técnico

### Fase 1 — MVP (atual)
- [x] Extração regex + LLM multi-provedor
- [x] API REST + Dashboard Streamlit
- [x] Dados: Visa, MC, Amex, Elo, Hipercard, BCB
- [x] Testes unitários + integração
- [x] DAG Airflow

### Fase 2 — Médio Prazo
- [ ] OCR (pytesseract) para PDFs escaneados
- [ ] Document AI (Google / AWS Textract) para tabelas complexas
- [ ] NER customizado para entidades de intercâmbio
- [ ] Knowledge Graph: Bandeira → Produto → Regra → Segmento

### Fase 3 — Longo Prazo (Nível Doctoral)
- [ ] Fine-tuning de LLM em corpus de manuais BR
- [ ] RAG (Retrieval-Augmented Generation) para consultas em linguagem natural
- [ ] Diff semântico entre versões de documentos
- [ ] Integração com API pública PAAR do BCB
