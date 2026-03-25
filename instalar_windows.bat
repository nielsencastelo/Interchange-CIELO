@echo off
REM ============================================================
REM  Interchange AI — Instalação no Windows
REM  Execute este arquivo como Administrador (ou em venv ativo)
REM ============================================================

echo.
echo ============================================================
echo  INTERCHANGE AI — INSTALACAO WINDOWS
echo ============================================================
echo.

REM Verifica se Python está disponível
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale em https://python.org
    pause
    exit /b 1
)

echo [1/5] Criando ambiente virtual...
python -m venv .venv
if errorlevel 1 (
    echo [AVISO] Falha ao criar venv. Continuando sem ele...
) else (
    echo [OK] Ambiente virtual criado em .venv\
    call .venv\Scripts\activate.bat
    echo [OK] Ambiente virtual ativado.
)

echo.
echo [2/5] Atualizando pip...
python -m pip install --upgrade pip --quiet

echo.
echo [3/5] Instalando dependencias principais...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha na instalacao. Tente manualmente:
    echo   pip install fastapi uvicorn sqlalchemy pandas pydantic pydantic-settings
    echo   pip install pdfplumber pypdf httpx streamlit plotly jinja2 pytest
    pause
    exit /b 1
)

echo.
echo [4/5] Copiando configuracoes...
if not exist .env (
    copy .env.example .env
    echo [OK] Arquivo .env criado. Edite com sua ANTHROPIC_API_KEY se desejar.
) else (
    echo [OK] .env ja existe, mantendo.
)

echo.
echo [5/5] Carregando dados de amostra no banco...
python -m src.seed_sample_data
if errorlevel 1 (
    echo [ERRO] Falha ao carregar dados. Verifique os logs acima.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  INSTALACAO CONCLUIDA!
echo ============================================================
echo.
echo  Para EXECUTAR o projeto, use os comandos abaixo:
echo.
echo  [TESTES]
echo    python -m pytest tests/ -v
echo.
echo  [API REST]
echo    uvicorn src.api.main:app --reload --port 8000
echo    Acesse: http://localhost:8000/docs
echo.
echo  [DASHBOARD]
echo    streamlit run src/dashboard.py
echo    Acesse: http://localhost:8501
echo.
echo  [RELATORIO HTML]
echo    python -m src.reports.generator
echo.
echo  [ANALISE EXPLORATORIA]
echo    python notebooks/exploratory_analysis.py
echo.
echo ============================================================
pause
