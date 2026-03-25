# 🪟 Interchange AI — Guia de Instalação no Windows

## Pré-requisitos

| Requisito | Como instalar |
|-----------|--------------|
| Python 3.10+ | https://python.org/downloads — marque **"Add Python to PATH"** |
| Git (opcional) | https://git-scm.com |

Verifique após instalar:
```cmd
python --version
pip --version
```

---

## Instalação Rápida (recomendado)

Abra o Prompt de Comando (`cmd`) ou PowerShell **na pasta do projeto** e execute:

```cmd
instalar_windows.bat
```

Isso cria o ambiente virtual, instala as dependências e carrega os dados de amostra.

---

## Instalação Manual (passo a passo)

### 1. Criar e ativar ambiente virtual

```cmd
python -m venv .venv
.venv\Scripts\activate
```

> No PowerShell, se der erro de política de execução:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> .venv\Scripts\Activate.ps1
> ```

### 2. Instalar dependências

```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

```cmd
copy .env.example .env
notepad .env
```

Deixe `DATABASE_URL=sqlite+pysqlite:///./interchange_ai.db` (padrão — sem Docker).

### 4. Carregar dados de amostra

```cmd
python -m src.seed_sample_data
```

---

## Executar o Projeto

### Menu interativo (mais fácil)

```cmd
executar_windows.bat
```

### Manualmente

**Rodar testes:**
```cmd
python -m pytest tests/ -v
```
> ⚠️ Use `python -m pytest`, não apenas `pytest` (evita o erro "'pytest' is not recognized")

**API REST:**
```cmd
uvicorn src.api.main:app --reload --port 8000
```
Acesse: http://localhost:8000/docs

**Dashboard:**
```cmd
streamlit run src/dashboard.py
```
Acesse: http://localhost:8501

**Relatório HTML:**
```cmd
python -m src.reports.generator
```

**Análise exploratória:**
```cmd
python notebooks/exploratory_analysis.py
```

---

## Solução de Problemas Comuns

### ❌ `'pytest' is not recognized`

Use sempre:
```cmd
python -m pytest tests/ -v
```

### ❌ `ModuleNotFoundError: No module named 'sqlalchemy'`

As dependências não foram instaladas no Python correto. Verifique:
```cmd
python -m pip list | findstr sqlalchemy
```

Se não aparecer, reinstale:
```cmd
python -m pip install -r requirements.txt
```

### ❌ `ModuleNotFoundError: No module named 'psycopg'`

**Causa:** `DATABASE_URL` aponta para PostgreSQL mas o driver não está instalado.

**Solução A (mais simples):** Use SQLite (padrão, zero config):
```dotenv
# No arquivo .env:
DATABASE_URL=sqlite+pysqlite:///./interchange_ai.db
```

**Solução B:** Instale o driver PostgreSQL:
```cmd
pip install psycopg2-binary
```

### ❌ `uvicorn: error: unrecognized arguments`

Certifique-se de estar dentro da pasta do projeto:
```cmd
cd C:\caminho\para\interchange_ai
uvicorn src.api.main:app --reload --port 8000
```

### ❌ Erro de importação `from ..database import`

O projeto usa imports relativos — **sempre execute como módulo**, nunca diretamente:

```cmd
# ✅ Correto
python -m src.seed_sample_data
python -m src.pipeline --input data/visa_sample.txt --network Visa

# ❌ Errado
python src/seed_sample_data.py
```

### ❌ `streamlit: command not found` no PowerShell

```cmd
python -m streamlit run src/dashboard.py
```

### ❌ Erro de encoding no Windows (caracteres especiais)

Adicione ao início do `.env`:
```dotenv
PYTHONIOENCODING=utf-8
```

Ou execute com:
```cmd
set PYTHONIOENCODING=utf-8
python -m src.seed_sample_data
```

---

## Estrutura de Comandos — Resumo Rápido

| O que fazer | Comando Windows |
|------------|----------------|
| Instalar tudo | `instalar_windows.bat` |
| Menu interativo | `executar_windows.bat` |
| Rodar testes | `python -m pytest tests/ -v` |
| Iniciar API | `uvicorn src.api.main:app --reload --port 8000` |
| Iniciar Dashboard | `python -m streamlit run src/dashboard.py` |
| Gerar relatório | `python -m src.reports.generator` |
| Análise exploratória | `python notebooks/exploratory_analysis.py` |
| Resetar banco | `python -m src.seed_sample_data --reset` |
| Extrair PDF | `python -m src.pipeline --input arquivo.pdf --network Visa --save` |

---

## Usando LLM (Anthropic Claude, OpenAI, Gemini, Ollama)

Edite o `.env` e defina sua chave:

```dotenv
# Para Anthropic Claude (recomendado):
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ENABLE_LLM_NORMALIZATION=true

# Para OpenAI:
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
ENABLE_LLM_NORMALIZATION=true

# Para Ollama local (grátis, instale em https://ollama.ai):
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
ENABLE_LLM_NORMALIZATION=true
```

Então extraia um documento:
```cmd
python -m src.pipeline --input data/visa_sample.txt --network Visa --use-llm --save
```
