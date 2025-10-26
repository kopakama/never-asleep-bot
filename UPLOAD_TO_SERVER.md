# 📤 Загрузка на удаленный сервер

## Способ 1: Через SCP (Windows - PowerShell)

### Подключение и загрузка файлов

```powershell
# 1. Перейдите в директорию проекта
cd E:\work\git\tg-alarm

# 2. Загрузите файлы на сервер
scp bot.py requirements.txt deploy.sh user@your-server-ip:~/telegram-bot/

# 3. Загрузите .env файл
scp .env user@your-server-ip:~/telegram-bot/.env

# 4. Подключитесь к серверу
ssh user@your-server-ip

# 5. На сервере
cd ~/telegram-bot
chmod +x deploy.sh
./deploy.sh
```

## Способ 2: Через SFTP клиент (FileZilla, WinSCP)

### Настройки подключения:
- **Протокол**: SFTP
- **Хост**: your-server-ip
- **Порт**: 22
- **Пользователь**: ваш_логин
- **Пароль**: ваш_пароль

### Загрузите файлы:
- `bot.py`
- `requirements.txt`
- `docker-compose.yml` (если используете Docker)
- `Dockerfile` (если используете Docker)
- `.env` (создайте на сервере вручную)

## Способ 3: Через Git (рекомендуется)

### Шаг 1: Загрузите код на GitHub

```bash
# Создайте репозиторий на GitHub
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/your-username/telegram-bot.git
git push -u origin main
```

### Шаг 2: На сервере

```bash
# Подключитесь к серверу
ssh user@your-server-ip

# Установите Git
sudo apt install git

# Клонируйте репозиторий
git clone https://github.com/your-username/telegram-bot.git
cd telegram-bot

# Создайте .env файл
nano .env
# Добавьте: TELEGRAM_BOT_TOKEN=your_token

# Запустите деплой
chmod +x deploy.sh
./deploy.sh
```

## Способ 4: Полная автоматизация (SCP скрипт для Windows)

Сохраните в `upload.ps1`:

```powershell
# Параметры подключения
$server = "user@your-server-ip"
$remotePath = "~/telegram-bot"

# Файлы для загрузки
$files = @("bot.py", "requirements.txt", "deploy.sh", "docker-compose.yml", "Dockerfile")

Write-Host "Загрузка файлов на сервер..."

# Создаем директорию на сервере
ssh $server "mkdir -p $remotePath"

# Загружаем файлы
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "Загружаем: $file"
        scp $file "$server`:$remotePath/"
    }
}

Write-Host "Загрузка завершена!"
Write-Host "Подключитесь к серверу: ssh $server"
Write-Host "Запустите: cd $remotePath && ./deploy.sh"
```

## Список файлов для загрузки

### Обязательные:
- ✅ `bot.py` - основной файл
- ✅ `requirements.txt` - зависимости
- ✅ `.env` - переменные окружения (СОЗДАЙТЕ НА СЕРВЕРЕ!)

### Для Docker:
- ✅ `docker-compose.yml`
- ✅ `Dockerfile`

### Для автоматического деплоя:
- ✅ `deploy.sh`
- ✅ `telegram-bot.service` (для systemd)

### Опциональные:
- `README.md`
- `DEPLOY.md`
- `QUICK_DEPLOY.md`

## Быстрая команда

Если у вас есть доступ к серверу, выполните:

```bash
# Одной командой (на вашем компьютере)
cd E:\work\git\tg-alarm
tar -czf bot.tar.gz bot.py requirements.txt deploy.sh docker-compose.yml Dockerfile telegram-bot.service
scp bot.tar.gz user@server:~/bot.tar.gz
ssh user@server "mkdir -p ~/telegram-bot && tar -xzf ~/bot.tar.gz -C ~/telegram-bot && cd ~/telegram-bot && echo 'TELEGRAM_BOT_TOKEN=your_token' > .env && chmod +x deploy.sh && ./deploy.sh"
```

## Проверка загрузки

После загрузки проверьте:

```bash
# На сервере
ssh user@your-server-ip
ls -la ~/telegram-bot

# Должны быть файлы:
# - bot.py
# - requirements.txt
# - deploy.sh
# - .env
```

## Следующие шаги

1. Загрузите файлы на сервер
2. Создайте `.env` файл с токеном
3. Запустите `./deploy.sh`
4. Проверьте логи: `sudo journalctl -u telegram-bot -f`

**Готово! Бот работает на сервере! 🚀**

