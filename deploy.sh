#!/bin/bash
# Скрипт для быстрого деплоя бота

set -e

echo "========================================="
echo "  Telegram Bot - Deploy Script"
echo "========================================="

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 не установлен!"
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "Создаем .env файл..."
    read -p "Введите TELEGRAM_BOT_TOKEN: " token
    echo "TELEGRAM_BOT_TOKEN=$token" > .env
    echo "✅ Файл .env создан"
fi

# Проверяем наличие модуля venv
if ! python3 -m venv --help &> /dev/null; then
    echo "Устанавливаем python3-venv..."
    sudo apt-get update
    sudo apt-get install -y python3-venv
fi

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "Создаем виртуальное окружение..."
    python3 -m venv venv
    echo "✅ Виртуальное окружение создано"
fi

# Активируем виртуальное окружение
echo "Активируем виртуальное окружение..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "ОШИБКА: Не найден venv/bin/activate"
    echo "Пробуем пересоздать виртуальное окружение..."
    rm -rf venv
    python3 -m venv venv
    source venv/bin/activate
fi

# Устанавливаем зависимости
echo "Устанавливаем зависимости..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Зависимости установлены"

# Останавливаем старый процесс если есть
if pgrep -f "python bot.py" > /dev/null; then
    echo "Останавливаем старый процесс..."
    pkill -f "python bot.py"
    sleep 2
fi

# Запускаем бота
echo "Запускаем бота..."
nohup python bot.py > bot.log 2>&1 &

echo "========================================="
echo "✅ Бот запущен!"
echo "========================================="
echo "Логи: tail -f bot.log"
echo "Остановить: pkill -f 'python bot.py'"
echo "========================================="

