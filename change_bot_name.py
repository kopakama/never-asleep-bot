#!/usr/bin/env python3
"""
Скрипт для изменения имени и аватарки бота через Bot API
ТРЕБУЕТСЯ: python-telegram-bot и токен бота
"""

import os
import requests
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def set_bot_name(token, name):
    """Устанавливает имя бота"""
    url = f"https://api.telegram.org/bot{token}/setMyName"
    params = {"name": name}
    response = requests.get(url, params=params)
    return response.json()

def set_bot_description(token, description):
    """Устанавливает описание бота"""
    url = f"https://api.telegram.org/bot{token}/setMyDescription"
    params = {"description": description}
    response = requests.get(url, params=params)
    return response.json()

def set_bot_short_description(token, short_description):
    """Устанавливает краткое описание бота"""
    url = f"https://api.telegram.org/bot{token}/setMyShortDescription"
    params = {"short_description": short_description}
    response = requests.get(url, params=params)
    return response.json()

def set_bot_commands(token):
    """Устанавливает команды бота"""
    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    commands = [
        {"command": "start", "description": "Начать работу с ботом"},
        {"command": "set", "description": "Установить будильник на время"},
        {"command": "stop", "description": "Остановить все будильники"},
        {"command": "status", "description": "Показать активные будильники"}
    ]
    data = {"commands": commands}
    response = requests.post(url, json=data)
    return response.json()

def main():
    if not TOKEN:
        print("ОШИБКА: TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    print("Изменяем настройки бота...")
    
    # Имя бота
    result = set_bot_name(TOKEN, "Будильник")
    print(f"Имя: {result}")
    
    # Описание
    description = """⏰ Будильник со спам-режимом!
Установите время и бот будет звонить каждые 5 секунд пока не скажете стоп."""
    result = set_bot_description(TOKEN, description)
    print(f"Описание: {result}")
    
    # Краткое описание
    short_desc = "Будильник со спам-режимом"
    result = set_bot_short_description(TOKEN, short_desc)
    print(f"Краткое описание: {result}")
    
    # Команды
    result = set_bot_commands(TOKEN)
    print(f"Команды: {result}")
    
    print("\n[OK] Настройки бота обновлены!")
    print("\n[INFO] Для изменения аватарки используйте @BotFather:")
    print("   1. Откройте @BotFather")
    print("   2. Отправьте: /setuserpic")
    print("   3. Выберите вашего бота")
    print("   4. Загрузите картинку")

if __name__ == "__main__":
    main()

