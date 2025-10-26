# ⚡ Быстрый деплой на удаленный сервер

## Способ 1: Linux VPS (самый простой)

### Шаг 1: Подключение к серверу
```bash
ssh user@your-server-ip
```

### Шаг 2: Установка зависимостей
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### Шаг 3: Загрузка бота
```bash
# Создаем директорию
mkdir -p ~/telegram-bot && cd ~/telegram-bot

# Загружаем файлы (скопируйте их через SCP или git)
# Или используйте git:
git clone <your-repo> .
```

### Шаг 4: Настройка и запуск
```bash
# Делаем скрипт исполняемым
chmod +x deploy.sh

# Запускаем деплой
./deploy.sh
```

**Всё! Бот запущен и работает.**

---

## Способ 2: Docker (рекомендуется)

### Шаг 1: Загрузка файлов на сервер
```bash
scp -r . user@your-server:~/telegram-bot/
ssh user@your-server
cd ~/telegram-bot
```

### Шаг 2: Создание .env файла
```bash
nano .env
```

Добавьте:
```
TELEGRAM_BOT_TOKEN=your_token_here
```

### Шаг 3: Запуск через Docker
```bash
# Запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

---

## Способ 3: Автоматический запуск (systemd)

### Шаг 1: Создаем пользователя (если нужно)
```bash
sudo adduser telegram-bot
sudo su - telegram-bot
```

### Шаг 2: Загружаем файлы
```bash
cd ~
git clone <your-repo> telegram-bot
cd telegram-bot
```

### Шаг 3: Устанавливаем зависимости
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Шаг 4: Настраиваем .env
```bash
nano .env
# Добавьте TELEGRAM_BOT_TOKEN=your_token
```

### Шаг 5: Устанавливаем systemd сервис
```bash
# Создаем сервис
sudo cp telegram-bot.service /etc/systemd/system/

# Заменяем %i на имя пользователя
sudo sed -i "s/%i/telegram-bot/g" /etc/systemd/system/telegram-bot.service

# Перезагружаем systemd
sudo systemctl daemon-reload

# Запускаем бота
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot

# Проверяем статус
sudo systemctl status telegram-bot
```

### Управление ботом
```bash
# Запустить
sudo systemctl start telegram-bot

# Остановить
sudo systemctl stop telegram-bot

# Перезапустить
sudo systemctl restart telegram-bot

# Логи
sudo journalctl -u telegram-bot -f
```

---

## Способ 4: Облачные платформы

### Railway.app
1. Зарегистрируйтесь на [railway.app](https://railway.app)
2. Создайте новый проект
3. Подключите GitHub репозиторий
4. Добавьте переменную `TELEGRAM_BOT_TOKEN`
5. Railway автоматически деплоит

### Render.com
1. Зарегистрируйтесь на [render.com](https://render.com)
2. Создайте новый Web Service
3. Подключите GitHub репозиторий
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python bot.py`
6. Добавьте переменную `TELEGRAM_BOT_TOKEN`

### Heroku
```bash
heroku login
heroku create your-bot-name
heroku config:set TELEGRAM_BOT_TOKEN=your_token
git push heroku main
heroku logs --tail
```

---

## Проверка работы

После деплоя проверьте:

1. **Найдите бота в Telegram**: @NeverAsleepBot
2. **Отправьте команду**: `/start`
3. **Установите тестовый будильник** на ближайшие 2-3 минуты

Если бот отвечает - всё работает! ✅

---

## Логи и мониторинг

### Просмотр логов
```bash
# systemd
sudo journalctl -u telegram-bot -f

# Docker
docker-compose logs -f

# Ручной запуск
tail -f bot.log
```

### Проверка процесса
```bash
# Проверить, что процесс запущен
ps aux | grep "python bot.py"

# Остановить все процессы
pkill -f "python bot.py"
```

---

## Полезные команды

```bash
# Перезапустить бота (systemd)
sudo systemctl restart telegram-bot

# Посмотреть последние логи
sudo journalctl -u telegram-bot --lines=50

# Проверить базу данных
ls -lh alarms.db
sqlite3 alarms.db ".tables"

# Обновить код
cd ~/telegram-bot
git pull
sudo systemctl restart telegram-bot
```

---

## Troubleshooting

### Бот не отвечает
```bash
# Проверить статус
sudo systemctl status telegram-bot

# Проверить логи
sudo journalctl -u telegram-bot -n 100

# Проверить токен
cat .env

# Перезапустить
sudo systemctl restart telegram-bot
```

### Ошибка "Conflict: only one bot instance"
```bash
# Остановить все процессы
pkill -f "python bot.py"

# Запустить заново
sudo systemctl start telegram-bot
```

### База данных не сохраняется
```bash
# Проверьте права на файл
ls -la alarms.db

# Установите правильные права
chmod 664 alarms.db
```

---

## Security Checklist

- [ ] Файл .env не в git
- [ ] Firewall настроен
- [ ] SSH ключи вместо пароля
- [ ] Регулярные бэкапы базы данных
- [ ] Мониторинг логов

---

## Backup базы данных

```bash
# Создать бэкап
cp alarms.db alarms_$(date +%Y%m%d).db

# Автоматический бэкап (crontab)
0 2 * * * cp /home/user/telegram-bot/alarms.db /backup/alarms_$(date +\%Y\%m\%d).db
```

---

**Готово! Ваш бот работает на сервере! 🚀**

