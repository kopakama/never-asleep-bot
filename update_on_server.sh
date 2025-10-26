#!/bin/bash
# Скрипт для обновления бота на сервере

echo "========================================="
echo "  Обновление Telegram Bot на сервере"
echo "========================================="

# Определяем директорию бота
BOT_DIR="${1:-~/telegram-bot}"

cd "$BOT_DIR" || { echo "ОШИБКА: Директория не найдена: $BOT_DIR"; exit 1; }

echo "Текущая директория: $(pwd)"
echo ""

# Останавливаем бота если запущен
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "Останавливаем бота..."
    pkill -f "python.*bot.py"
    sleep 2
fi

# Обновляем код из Git
echo "Обновляем код из Git..."
git pull origin main

# Проверяем наличие изменений
if [ $? -eq 0 ]; then
    echo "✅ Код обновлен!"
    echo ""
    
    # Устанавливаем зависимости если requirements изменился
    echo "Проверяем зависимости..."
    if [ -f requirements.txt ]; then
        pip3 install -r requirements.txt --user --upgrade --quiet
        echo "✅ Зависимости обновлены"
    fi
    
    # Запускаем бота
    echo ""
    echo "Запускаем бота..."
    
    if [ -f deploy_simple.sh ]; then
        chmod +x deploy_simple.sh
        ./deploy_simple.sh
    else
        # Запуск в фоне
        nohup python3 bot.py > bot.log 2>&1 &
        sleep 2
        
        if pgrep -f "python.*bot.py" > /dev/null; then
            echo "✅ Бот запущен!"
            echo "PID: $(pgrep -f 'python.*bot.py')"
        else
            echo "❌ Бот не запустился. Проверьте логи: cat bot.log"
        fi
    fi
else
    echo "❌ Ошибка при обновлении кода!"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Обновление завершено!"
echo "========================================="

