@echo off
echo ====================================
echo  Telegram Bot Alarm - Запуск
echo ====================================
echo.

REM Проверяем наличие токена
if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo [ERROR] TELEGRAM_BOT_TOKEN не установлен!
    echo.
    echo Установите токен одним из способов:
    echo 1. Создайте файл .env с содержимым: TELEGRAM_BOT_TOKEN=ваш_токен
    echo 2. Или установите переменную окружения:
    echo    set TELEGRAM_BOT_TOKEN=ваш_токен
    echo.
    pause
    exit /b 1
)

echo Токен найден. Запускаем бота...
echo.

REM Активация виртуального окружения (если есть)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Запуск бота
python bot.py

pause

