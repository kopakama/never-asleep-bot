#!/bin/bash
# Упрощенный скрипт деплоя без виртуального окружения

set -e

echo "========================================="
echo "  Telegram Bot - Simple Deploy"
echo "========================================="

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "ОШИБКА: Python3 не установлен!"
    echo "Установите: sudo apt-get install python3 python3-pip"
    exit 1
fi

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "Создаем .env файл..."
    read -p "Введите TELEGRAM_BOT_TOKEN: " token
    echo "TELEGRAM_BOT_TOKEN=$token" > .env
    echo "✅ Файл .env создан"
fi

# Устанавливаем зависимости (глобально)
echo "Устанавливаем зависимости..."
pip3 install --user --upgrade pip
pip3 install --user -r requirements.txt
echo "✅ Зависимости установлены"

# Останавливаем старый процесс если есть
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "Останавливаем старый процесс..."
    pkill -f "python.*bot.py"
    sleep 2
fi

# Запускаем бота
echo "Запускаем бота..."
nohup python3 bot.py > bot.log 2>&1 &

sleep 2

echo "========================================="
echo "✅ Бот запущен!"
echo "========================================="
echo "Проверка статуса:"
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "✅ Процесс запущен"
    echo "PID: $(pgrep -f 'python.*bot.py')"
else
    echo "❌ Процесс не запущен"
    echo "Проверьте логи: cat bot.log"
fi
echo "========================================="
echo "Логи: tail -f bot.log"
echo "Остановить: pkill -f 'python.*bot.py'"
echo "========================================="

