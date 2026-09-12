@echo off
rem ---------------------------------------------------------------------------
rem  Control Horario - instalador para Windows
rem  Haz doble clic en este archivo para instalar el programa.
rem ---------------------------------------------------------------------------
title Instalar Control Horario
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
if errorlevel 1 (
    echo.
    echo La instalacion no ha terminado correctamente.
    pause
)
