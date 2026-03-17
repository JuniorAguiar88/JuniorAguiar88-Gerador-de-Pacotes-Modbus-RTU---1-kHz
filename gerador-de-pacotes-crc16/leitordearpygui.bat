@echo off
chcp 65001 >nul
title Contador Modbus RTU - Interface Gráfica
color 0A

echo ========================================
echo   CONTADOR MODBUS RTU COM TENSÕES
echo ========================================
echo   Interface DearPyGUI
echo ========================================
echo.
echo Verificando ambiente Python...

REM Verifica se o Python está instalado
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Python encontrado
    set PYTHON_CMD=python
) else (
    python3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Python3 encontrado
        set PYTHON_CMD=python3
    ) else (
        echo ❌ Python não encontrado!
        echo.
        echo Por favor, instale o Python:
        echo 1. Acesse: https://python.org
        echo 2. Baixe e instale Python 3.8+
        echo 3. Marque a opção "Add Python to PATH"
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Verificando dependências...



echo.
echo ========================================
echo Iniciando Contador Modbus...
echo ========================================
echo.
echo Arquivo: leitordearpygui.py
echo Interface: DearPyGUI
echo Porta padrão: COM7
echo.
echo Pressione Ctrl+C na janela do programa para sair
echo.

REM Executa o programa
%PYTHON_CMD% "leitordearpygui.py"

REM Verifica o código de retorno
if %errorlevel% equ 0 (
    echo.
    echo ✅ Programa encerrado normalmente
) else if %errorlevel% equ 1 (
    echo.
    echo ⚠️  Programa encerrado com avisos
) else (
    echo.
    echo ❌ Programa encerrado com erro (código: %errorlevel%)
)

echo.
pause