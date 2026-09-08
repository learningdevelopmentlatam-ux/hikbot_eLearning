@echo off
cd /d "%~dp0"
echo Generando datos desde la base de datos...
python hik_export.py
echo Abriendo dashboard...
start http://localhost:8080/hik_dashboard.html
python -m http.server 8080