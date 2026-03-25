@echo off
REM ============================================================
REM  Interchange AI — Menu de Execucao Windows
REM ============================================================

REM Ativa venv se existir
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

:menu
echo.
echo ============================================================
echo  INTERCHANGE AI — MENU
echo ============================================================
echo.
echo  [1] Rodar TESTES (pytest)
echo  [2] Iniciar API REST  (http://localhost:8000/docs)
echo  [3] Iniciar DASHBOARD (http://localhost:8501)
echo  [4] Gerar RELATORIO HTML
echo  [5] Analise Exploratoria
echo  [6] Recarregar dados de amostra
echo  [0] Sair
echo.
set /p opcao="Escolha uma opcao: "

if "%opcao%"=="1" goto testes
if "%opcao%"=="2" goto api
if "%opcao%"=="3" goto dashboard
if "%opcao%"=="4" goto relatorio
if "%opcao%"=="5" goto analise
if "%opcao%"=="6" goto seed
if "%opcao%"=="0" exit /b 0
goto menu

:testes
echo.
echo Executando testes...
python -m pytest tests/ -v
pause
goto menu

:api
echo.
echo Iniciando API em http://localhost:8000
echo Swagger UI em http://localhost:8000/docs
echo Pressione CTRL+C para parar.
echo.
uvicorn src.api.main:app --reload --port 8000
pause
goto menu

:dashboard
echo.
echo Iniciando Dashboard em http://localhost:8501
echo Pressione CTRL+C para parar.
echo.
streamlit run src/dashboard.py
pause
goto menu

:relatorio
echo.
echo Gerando relatorio HTML...
python -m src.reports.generator
echo Abra o arquivo relatorio_intercambio.html no navegador.
pause
goto menu

:analise
echo.
echo Executando analise exploratoria...
python notebooks/exploratory_analysis.py
pause
goto menu

:seed
echo.
echo Recarregando dados de amostra...
python -m src.seed_sample_data --reset
pause
goto menu
