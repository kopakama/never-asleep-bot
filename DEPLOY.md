# 🚀 Деплой бота на удаленный сервер

## Вариант 1: Обычный VPS/Linux сервер (Ubuntu/Debian)

### 1. Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Python и pip
sudo apt install python3 python3-pip python3-venv -y

# Создаем директорию для бота
mkdir -p ~/telegram-bot
cd ~/telegram-bot
```

### 2. Загрузка файлов на сервер

**Вариант A: Через Git**
```bash
git clone <your-repo-url> .
# Или загрузите файлы через SFTP/SCP
```

**Вариант B: Через SCP (с локального компьютера)**
```bash
scp bot.py requirements.txt .gitignore user@your-server:/home/user/telegram-bot/
```

### 3. Установка зависимостей

```bash
cd ~/telegram-bot

# Создаем виртуальное окружение (опционально)
python3 -m venv venv
source venv/bin/activate  # или на Windows: venv\Scripts\activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

```bash
# Создаем файл .env
nano .env
```

Добавьте в файл:
```
TELEGRAM_BOT_TOKEN=ваш_токен_здесь
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

### 5. Создание systemd сервиса

```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

Добавьте содержимое:
```ini
[Unit]
Description=Telegram Alarm Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/telegram-bot
Environment="PATH=/home/your-username/telegram-bot/venv/bin"
ExecStart=/home/your-username/telegram-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Сохраните и замените `your-username` на ваш логин.

### 6. Запуск бота

```bash
# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable telegram-bot

# Запускаем бота
sudo systemctl start telegram-bot

# Проверяем статус
sudo systemctl status telegram-bot

# Просмотр логов
sudo journalctl -u telegram-bot -f
```

### 7. Управление ботом

```bash
# Остановить бота
sudo systemctl stop telegram-bot

# Перезапустить бота
sudo systemctl restart telegram-bot

# Посмотреть логи
sudo journalctl -u telegram-bot --lines=50
```

---

## Вариант 2: Docker (рекомендуется)

### 1. Создайте Dockerfile в корне проекта

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY bot.py .

# Запускаем бота
CMD ["python", "bot.py"]
```

### 2. Запуск через Docker

```bash
# Создайте docker-compose.yml
cat > docker-compose.yml << EOF
version: '3.8'

services:
  telegram-bot:
    build: .
    restart: always
    env_file:
      - .env
    volumes:
      - ./alarms.db:/app/alarms.db
EOF

# Запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

### 3. Docker Compose команды

```bash
# Запустить
docker-compose up -d

# Остановить
docker-compose down

# Перезапустить
docker-compose restart

# Логи
docker-compose logs -f telegram-bot
```

---

## Вариант 3: Cloud платформы

### Railway.app

1. Создайте аккаунт на [Railway.app](https://railway.app)
2. Создайте новый проект
3. Подключите GitHub репозиторий
4. Добавьте переменную окружения `TELEGRAM_BOT_TOKEN`
5. Railway автоматически деплоит

### Heroku

```bash
# Установите Heroku CLI
heroku login

# Создайте приложение
heroku create your-bot-name

# Добавьте переменную окружения
heroku config:set TELEGRAM_BOT_TOKEN=your_token

# Запушьте код
git push heroku main

# Логи
heroku logs --tail
```

### Render.com

1. Создайте аккаунт на [Render.com](https://render.com)
2. Новый Web Service
3. Подключите GitHub репозиторий
4. Настройки:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
5. Добавьте переменную `TELEGRAM_BOT_TOKEN`

---

## Безопасность

### 1. Firewall (UFW)

```bash
# Устанавливаем UFW
sudo apt install ufw

# Разрешаем SSH
sudo ufw allow 22/tcp

# Включаем firewall
sudo ufw enable

# Проверяем статус
sudo ufw status
```

### 2. Файл .env в .gitignore

Убедитесь, что `.env` в `.gitignore`:
```
.env
*.db
__pycache__/
```

### 3. Nginx reverse proxy (опционально)

Если используете webhook вместо polling:

```bash
sudo apt install nginx

sudo nano /etc/nginx/sites-available/telegram-bot
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Мониторинг

### 1. Логи

```bash
# systemd
journalctl -u telegram-bot -f

# Docker
docker logs -f telegram-bot

# Стандартный вывод
tail -f nohup.out
```

### 2. Healthcheck скрипт

Создайте `health_check.sh`:

```bash
#!/bin/bash
if ! pgrep -f "python bot.py" > /dev/null; then
    echo "Bot is down! Restarting..."
    systemctl restart telegram-bot
fi
```

Добавьте в crontab:
```bash
crontab -e
# Добавьте строку:
*/5 * * * * /path/to/health_check.sh
```

---

## Troubleshooting

### Бот не отвечает

```bash
# Проверьте, что бот запущен
ps aux | grep python

# Проверьте токен
cat .env

# Проверьте логи
journalctl -u telegram-bot -n 50
```

### Конфликт getUpdates

Остановите все процессы бота перед запуском:
```bash
pkill -f "python bot.py"
```

### Бот перезапускается постоянно

Проверьте логи на наличие ошибок:
```bash
sudo journalctl -u telegram-bot --since "1 hour ago"
```

---

## Быстрый старт (одна команда)

```bash
# На чистом Ubuntu/Debian
curl -fsSL https://raw.githubusercontent.com/your-repo/deploy.sh | bash
```

---

## Полезные ссылки

- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Systemd Service Tutorial](https://www.digitalocean.com/community/tutorials/how-to-use-systemd-to-manage-systemd-services-and-units)
- [Docker Tutorial](https://docs.docker.com/get-started/)

