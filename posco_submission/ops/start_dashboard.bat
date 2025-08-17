@echo off
cd /d %~dp0
cd ..\app
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate
streamlit run src\dashboard.py --server.port 8501
pause
