# 📁 Список файлов проекта

## Основные файлы (обязательные)

### Локальная разработка
- `bot.py` - основной файл бота
- `requirements.txt` - зависимости Python
- `.env` - переменные окружения (создайте локально)
- `start.bat` - скрипт запуска для Windows
- `alarms.db` - база данных (создается автоматически)

### Деплой на сервер
- `Dockerfile` - образ Docker
- `docker-compose.yml` - конфигурация Docker
- `deploy.sh` - скрипт автоматического деплоя (Linux/Mac)
- `telegram-bot.service` - systemd сервис для Linux

## Документация

### Основная документация
- `README.md` - главная документация проекта
- `QUICK_START.md` - быстрый старт
- `DEPLOY.md` - полная инструкция по деплою
- `QUICK_DEPLOY.md` - быстрый деплой
- `UPLOAD_TO_SERVER.md` - загрузка на сервер
- `FILES_LIST.md` - этот файл

### Служебные файлы
- `.gitignore` - игнорируемые Git файлы
- `.env.example` - пример файла окружения

## Структура проекта

```
tg-alarm/
├── bot.py                    # Основной файл бота
├── requirements.txt          # Зависимости
├── .env                     # Токен (создайте сами!)
├── alarms.db                # База данных (создается автоматически)
│
├── Docker
├── Dockerfile               # Образ Docker
├── docker-compose.yml       # Docker Compose конфиг
│
├── Deployment
├── deploy.sh               # Автодеплой скрипт
├── telegram-bot.service    # Systemd сервис
├── start.bat               # Windows запуск
│
└── Documentation
    ├── README.md
    ├── QUICK_START.md
    ├── DEPLOY.md
    ├── QUICK_DEPLOY.md
    ├── UPLOAD_TO_SERVER.md
    └── FILES_LIST.md
```

## Что загружать на сервер?

### Минимальный набор
```
bot.py
requirements.txt
.env
deploy.sh
```

### Docker вариант
```
bot.py
requirements.txt
.env
Dockerfile
docker-compose.yml
```

### Автозапуск (systemd)
```
bot.py
requirements.txt
.env
deploy.sh
telegram-bot.service
```

## Игнорируемые файлы

Следующие файлы НЕ нужно загружать (указаны в .gitignore):
- `.env` - содержит токен (создайте на сервере)
- `alarms.db` - база данных (создастся автоматически)
- `__pycache__/` - Python кэш
- `*.pyc` - скомпилированные файлы
- `venv/` - виртуальное окружение

## Быстрая проверка

### Перед деплоем убедитесь что у вас есть:
```bash
ls -la
# Проверьте наличие:
# ✅ bot.py
# ✅ requirements.txt
# ✅ .env (на сервере!)
# ✅ deploy.sh (для Linux)
# ✅ docker-compose.yml (для Docker)
```

### Минимальные требования
- Python 3.8+ или Docker
- Файл .env с токеном
- Доступ к интернету

