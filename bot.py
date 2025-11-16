import asyncio
import logging
import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения активных будильников {user_id: [список задач]}
active_alarms: Dict[int, List[asyncio.Task]] = {}

# Словарь для флагов спама {user_id: True/False}
spam_active: Dict[int, bool] = {}

# Функции для работы с часовыми поясами
def get_user_timezone(user_id: int) -> str:
    """Получает часовой пояс пользователя из БД, по умолчанию UTC"""
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('SELECT timezone FROM user_timezones WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'UTC'

def set_user_timezone(user_id: int, timezone: str) -> bool:
    """Устанавливает часовой пояс пользователя"""
    try:
        # Проверяем, что часовой пояс валидный
        ZoneInfo(timezone)
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_timezones (user_id, timezone)
            VALUES (?, ?)
        ''', (user_id, timezone))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке часового пояса: {e}")
        return False

def get_user_datetime_now(user_id: int) -> datetime:
    """Получает текущее время в часовом поясе пользователя"""
    timezone_str = get_user_timezone(user_id)
    tz = ZoneInfo(timezone_str)
    return datetime.now(tz)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            alarm_time TEXT NOT NULL,
            message TEXT,
            created_at TEXT NOT NULL,
            repeat_days TEXT
        )
    ''')
    # Добавляем колонку repeat_days если её нет (для существующих БД)
    try:
        cursor.execute('ALTER TABLE alarms ADD COLUMN repeat_days TEXT')
    except sqlite3.OperationalError:
        pass  # Колонка уже существует
    
    # Создаем таблицу для часовых поясов пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_timezones (
            user_id INTEGER PRIMARY KEY,
            timezone TEXT NOT NULL DEFAULT 'UTC'
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Загрузка сохраненных будильников из БД
async def load_saved_alarms(app: Application):
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, alarm_time, message, repeat_days FROM alarms')
    alarms = cursor.fetchall()
    conn.close()
    
    for user_id, alarm_time, message, repeat_days in alarms:
        try:
            alarm_datetime = datetime.strptime(alarm_time, "%H:%M")
            repeat_days_set = set(json.loads(repeat_days)) if repeat_days else None
            await schedule_alarm(app, user_id, alarm_datetime, message or "", repeat_days_set)
        except Exception as e:
            logger.error(f"Ошибка при загрузке будильника: {e}")

# Функция планирования будильника
async def schedule_alarm(app: Application, user_id: int, alarm_time: datetime, message: str = "", repeat_days: Optional[Set[int]] = None):
    """Планирует будильник на указанное время
    
    Args:
        app: Приложение бота
        user_id: ID пользователя
        alarm_time: Время будильника (только час и минута)
        message: Сообщение для будильника
        repeat_days: Множество дней недели (0=понедельник, 6=воскресенье) для повторяющихся будильников
    """
    # Получаем текущее время в часовом поясе пользователя
    now = get_user_datetime_now(user_id)
    # Создаем datetime с текущей датой и указанным временем из alarm_time в часовом поясе пользователя
    target = now.replace(hour=alarm_time.hour, minute=alarm_time.minute, second=0, microsecond=0)
    
    # Если время прошло и это не повторяющийся будильник
    if target < now:
        if repeat_days:
            # Для повторяющегося будильника находим следующий подходящий день
            target = find_next_repeat_day(target, repeat_days, now)
        else:
            # Для одноразового будильника планируем на завтра
            target = target + timedelta(days=1)
    
    # Если это повторяющийся будильник и сегодня подходящий день не найден
    if repeat_days and target.weekday() not in repeat_days:
        target = find_next_repeat_day(target, repeat_days, now)
    
    # Вычисляем задержку в секундах (конвертируем в UTC для расчета)
    now_utc = datetime.now(ZoneInfo('UTC'))
    target_utc = target.astimezone(ZoneInfo('UTC'))
    delay = (target_utc - now_utc).total_seconds()
    
    logger.info(f"Будильник запланирован для пользователя {user_id} на {target.strftime('%Y-%m-%d %H:%M %Z')} (повтор: {repeat_days is not None})")
    
    # Создаем задачу
    task = asyncio.create_task(
        send_alarm(app, user_id, alarm_time, message, delay, repeat_days)
    )
    
    # Сохраняем задачу
    if user_id not in active_alarms:
        active_alarms[user_id] = []
    active_alarms[user_id].append(task)

# Функция поиска следующего дня для повторяющегося будильника
def find_next_repeat_day(target: datetime, repeat_days: Set[int], now: datetime) -> datetime:
    """Находит следующий подходящий день для повторяющегося будильника"""
    # Проверяем дни начиная с сегодня до конца следующей недели
    for days_ahead in range(14):
        candidate = target + timedelta(days=days_ahead)
        # Если время в прошлом, пропускаем
        if candidate < now:
            continue
        # Проверяем, подходит ли день недели
        if candidate.weekday() in repeat_days:
            return candidate
    
    # Если ничего не найдено (не должно произойти), возвращаем следующий день
    return now + timedelta(days=1)

# Функция отправки спам-сообщений
async def spam_messages(app: Application, user_id: int, alarm_time: datetime, message: str):
    """Отправляет спам-сообщения каждые 2 секунды пока флаг активен"""
    spam_active[user_id] = True
    
    while spam_active.get(user_id, False):
        try:
            # Получаем текущее время в часовом поясе пользователя
            current_time = get_user_datetime_now(user_id).strftime("%H:%M:%S")
            alarm_text = f"⏰ БУДИЛЬНИК! Время: {alarm_time.strftime('%H:%M')}\n🕐 Сейчас: {current_time}"
            if message:
                alarm_text += f"\n💬 {message}"
            alarm_text += "\n\n❌ Напишите 'стоп' чтобы остановить"
            
            await app.bot.send_message(chat_id=user_id, text=alarm_text)
            logger.info(f"Будильник отправлен пользователю {user_id}")
            
            # Ждем 2 секунды перед следующим сообщением
            await asyncio.sleep(2)
            
        except asyncio.CancelledError:
            logger.info(f"Спам отменен для пользователя {user_id}")
            break
        except Exception as e:
            logger.error(f"Ошибка при отправке будильника: {e}")
            break

# Функция отправки будильника
async def send_alarm(app: Application, user_id: int, alarm_time: datetime, message: str, delay: float, repeat_days: Optional[Set[int]] = None):
    """Ждет указанное время и запускает спам"""
    try:
        # Ждем до наступления времени будильника
        await asyncio.sleep(delay)
        
        # Устанавливаем флаг активности
        spam_active[user_id] = True
        
        # Запускаем спам
        task = asyncio.create_task(
            spam_messages(app, user_id, alarm_time, message)
        )
        
        # Сохраняем задачу
        if user_id not in active_alarms:
            active_alarms[user_id] = []
        active_alarms[user_id].append(task)
        
        # Если это повторяющийся будильник, планируем следующий раз
        if repeat_days:
            await schedule_alarm(app, user_id, alarm_time, message, repeat_days)
        
    except asyncio.CancelledError:
        logger.info(f"Будильник отменен для пользователя {user_id}")
        spam_active[user_id] = False
    except Exception as e:
        logger.error(f"Ошибка при отправке будильника: {e}")

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    user_id = update.effective_user.id
    timezone = get_user_timezone(user_id)
    current_time = get_user_datetime_now(user_id).strftime("%H:%M:%S")
    
    keyboard = [
        [InlineKeyboardButton("⏰ Установить будильник", callback_data="set_alarm")],
        [InlineKeyboardButton("📊 Мои будильники", callback_data="status")],
        [InlineKeyboardButton("🛑 Остановить все", callback_data="stop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Привет! Я **Будильник** 📢\n\n"
        f"🌍 **Ваш часовой пояс:** `{timezone}`\n"
        f"🕐 **Текущее время:** `{current_time}`\n\n"
        "🎯 **Как это работает:**\n"
        "1. Установите время будильника\n"
        "2. Бот будет звонить каждые 2 секунды\n"
        "3. Напишите 'стоп' чтобы остановить\n\n"
        "📌 **Команды:**\n"
        "• `/set HH:MM [сообщение]` - одноразовый будильник\n"
        "• `/repeat HH:MM дни [сообщение]` - повторяющийся\n"
        "• `/timezone` - установить часовой пояс\n\n"
        "📌 **Примеры:**\n"
        "• `/set 08:30 Доброе утро!`\n"
        "• `/repeat 09:00 12345 Работа` - будни\n"
        "• `/repeat 12:00 67 Выходные`\n"
        "• `/timezone Europe/Moscow`\n\n"
        "Или используйте кнопки ниже 👇",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Обработчик команды /set
async def set_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает одноразовый будильник"""
    if not context.args:
        user_id = update.effective_user.id
        timezone = get_user_timezone(user_id)
        current_time = get_user_datetime_now(user_id).strftime("%H:%M")
        
        keyboard = [
            [InlineKeyboardButton("📝 Примеры", callback_data="set_examples")],
            [InlineKeyboardButton("🔄 Повторяющийся", callback_data="repeat_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⏰ **Установка одноразового будильника**\n\n"
            f"🌍 **Ваш часовой пояс:** `{timezone}`\n"
            f"🕐 **Текущее время:** `{current_time}`\n\n"
            "📝 **Формат команды:**\n"
            "`/set HH:MM [сообщение]`\n\n"
            "**Примеры:**\n"
            "• `/set 08:30` - будильник на 8:30\n"
            "• `/set 08:30 Доброе утро!` - с сообщением\n"
            "• `/set 14:00 Обед`\n"
            "• `/set 22:00 Время спать`\n\n"
            "💡 **Подсказка:** Время указывается в вашем часовом поясе",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    user_id = update.effective_user.id
    
    try:
        # Парсим время
        time_str = context.args[0].strip()
        
        # Проверяем и парсим формат времени
        alarm_time = None
        formats_to_try = ["%H:%M", "%H.%M", "%H %M"]
        
        for fmt in formats_to_try:
            try:
                alarm_time = datetime.strptime(time_str, fmt)
                break
            except ValueError:
                continue
        
        if alarm_time is None:
            raise ValueError(f"Неверный формат времени: {time_str}. Используйте HH:MM (например, 08:30 или 8:30)")
        
        # Получаем сообщение, если есть
        message = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        
        # Отменяем предыдущие будильники для пользователя
        if user_id in active_alarms:
            for task in active_alarms[user_id]:
                task.cancel()
            active_alarms[user_id] = []
        
        # Отменяем флаг спама если был установлен
        spam_active[user_id] = False
        
        # Планируем новый будильник (одноразовый, без repeat_days)
        await schedule_alarm(context.application, user_id, alarm_time, message, None)
        
        # Сохраняем в БД
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        # Удаляем старые будильники пользователя (только одноразовые)
        cursor.execute('DELETE FROM alarms WHERE user_id = ? AND (repeat_days IS NULL OR repeat_days = "")', (user_id,))
        # Добавляем новый
        now_user = get_user_datetime_now(user_id)
        cursor.execute(
            'INSERT INTO alarms (user_id, alarm_time, message, created_at, repeat_days) VALUES (?, ?, ?, ?, ?)',
            (user_id, alarm_time.strftime("%H:%M"), message, now_user.isoformat(), None)
        )
        conn.commit()
        conn.close()
        
        # Вычисляем время до будильника в часовом поясе пользователя
        now = get_user_datetime_now(user_id)
        # Создаем datetime с текущей датой и указанным временем
        target = now.replace(hour=alarm_time.hour, minute=alarm_time.minute, second=0, microsecond=0)
        
        if target < now:
            target = target + timedelta(days=1)
        
        time_until = target - now
        hours = int(time_until.total_seconds() // 3600)
        minutes = int((time_until.total_seconds() % 3600) // 60)
        
        # Формируем сообщение о времени до будильника
        time_text = ""
        if hours > 0:
            time_text += f"{hours} час(ов) "
        if minutes > 0:
            time_text += f"{minutes} минут(ы) "
        
        keyboard = [
            [InlineKeyboardButton("📊 Мои будильники", callback_data="status")],
            [InlineKeyboardButton("🛑 Остановить", callback_data="stop")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **Будильник установлен!**\n\n"
            f"⏰ **Время:** `{alarm_time.strftime('%H:%M')}`\n"
            f"⏳ **До будильника:** {time_text.strip() or 'менее минуты'}\n"
            f"📅 **Тип:** Одноразовый\n\n"
            f"📢 Бот будет отправлять сообщения каждые 2 секунды\n"
            f"❌ Для остановки: напишите 'стоп' или `/stop`\n\n"
            f"💡 Для повторяющегося будильника используйте `/repeat`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "формат времени" in error_msg.lower() or "hh:mm" in error_msg.lower():
            await update.message.reply_text(
                "❌ **Неверный формат времени!**\n\n"
                "📝 **Правильный формат:** `HH:MM`\n\n"
                "**Примеры правильного формата:**\n"
                "• `/set 08:30` ✅\n"
                "• `/set 8:30` ✅ (можно без ведущего нуля)\n"
                "• `/set 23:59` ✅\n"
                "• `/set 00:00` ✅\n\n"
                "❌ **Неправильно:**\n"
                "• `/set 8-30` ❌ (дефис вместо двоеточия)\n"
                "• `/set 830` ❌ (без разделителя)\n"
                "• `/set 8 30` ❌ (пробел вместо двоеточия)\n"
                "• `/set 25:00` ❌ (час больше 23)",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка: {error_msg}\n\n"
                "Используйте: `/set HH:MM [сообщение]`\n"
                "Пример: `/set 08:30`",
                parse_mode="Markdown"
            )

# Обработчик команды /repeat
async def set_repeat_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает повторяющийся будильник"""
    if not context.args or len(context.args) < 2:
        user_id = update.effective_user.id
        timezone = get_user_timezone(user_id)
        current_time = get_user_datetime_now(user_id).strftime("%H:%M")
        
        keyboard = [
            [InlineKeyboardButton("📝 Примеры", callback_data="repeat_examples")],
            [InlineKeyboardButton("⏰ Одноразовый", callback_data="set_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔄 **Установка повторяющегося будильника**\n\n"
            f"🌍 **Ваш часовой пояс:** `{timezone}`\n"
            f"🕐 **Текущее время:** `{current_time}`\n\n"
            "📝 **Формат команды:**\n"
            "`/repeat HH:MM дни [сообщение]`\n\n"
            "📅 **Формат дней (1-7):**\n"
            "• `1` = Понедельник\n"
            "• `2` = Вторник\n"
            "• `3` = Среда\n"
            "• `4` = Четверг\n"
            "• `5` = Пятница\n"
            "• `6` = Суббота\n"
            "• `7` = Воскресенье\n\n"
            "**Примеры:**\n"
            "• `/repeat 08:30 12345` - будни (Пн-Пт)\n"
            "• `/repeat 09:00 1234567` - каждый день\n"
            "• `/repeat 12:00 67` - выходные (Сб-Вс)\n"
            "• `/repeat 08:00 12345 Работа` - будни с сообщением\n\n"
            "💡 **Подсказка:** Время указывается в вашем часовом поясе",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    user_id = update.effective_user.id
    
    try:
        # Парсим время
        time_str = context.args[0].strip()
        
        # Проверяем и парсим формат времени
        alarm_time = None
        formats_to_try = ["%H:%M", "%H.%M", "%H %M"]
        
        for fmt in formats_to_try:
            try:
                alarm_time = datetime.strptime(time_str, fmt)
                break
            except ValueError:
                continue
        
        if alarm_time is None:
            raise ValueError(f"Неверный формат времени: {time_str}. Используйте HH:MM (например, 08:30 или 8:30)")
        
        # Парсим дни недели
        days_str = context.args[1]
        # Преобразуем из формата 1-7 в 0-6 (Python weekday)
        repeat_days_set = set()
        for day_char in days_str:
            if day_char.isdigit():
                day_num = int(day_char)
                if 1 <= day_num <= 7:
                    # Конвертируем: 1(Пн)=0, 2(Вт)=1, ..., 7(Вс)=6
                    repeat_days_set.add(day_num - 1)
        
        if not repeat_days_set:
            raise ValueError("Неверный формат дней недели")
        
        # Получаем сообщение, если есть
        message = " ".join(context.args[2:]) if len(context.args) > 2 else ""
        
        # Планируем новый будильник
        await schedule_alarm(context.application, user_id, alarm_time, message, repeat_days_set)
        
        # Сохраняем в БД
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        # Удаляем старые повторяющиеся будильники пользователя (с таким же временем)
        cursor.execute(
            'DELETE FROM alarms WHERE user_id = ? AND alarm_time = ? AND repeat_days IS NOT NULL AND repeat_days != ""',
            (user_id, alarm_time.strftime("%H:%M"))
        )
        # Добавляем новый
        now_user = get_user_datetime_now(user_id)
        cursor.execute(
            'INSERT INTO alarms (user_id, alarm_time, message, created_at, repeat_days) VALUES (?, ?, ?, ?, ?)',
            (user_id, alarm_time.strftime("%H:%M"), message, now_user.isoformat(), json.dumps(list(repeat_days_set)))
        )
        conn.commit()
        conn.close()
        
        # Вычисляем время до будильника в часовом поясе пользователя
        now = get_user_datetime_now(user_id)
        # Создаем datetime с текущей датой и указанным временем
        target = now.replace(hour=alarm_time.hour, minute=alarm_time.minute, second=0, microsecond=0)
        target = find_next_repeat_day(target, repeat_days_set, now)
        
        time_until = target - now
        hours = int(time_until.total_seconds() // 3600)
        minutes = int((time_until.total_seconds() % 3600) // 60)
        
        # Формируем сообщение о времени до будильника
        time_text = ""
        if hours > 0:
            time_text += f"{hours} час(ов) "
        if minutes > 0:
            time_text += f"{minutes} минут(ы) "
        
        days_text = format_days(json.dumps(list(repeat_days_set)))
        
        keyboard = [
            [InlineKeyboardButton("📊 Мои будильники", callback_data="status")],
            [InlineKeyboardButton("🛑 Остановить", callback_data="stop")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **Повторяющийся будильник установлен!**\n\n"
            f"⏰ **Время:** `{alarm_time.strftime('%H:%M')}`\n"
            f"📅 **Повтор:** {days_text}\n"
            f"⏳ **Следующий раз:** {time_text.strip() or 'менее минуты'}\n\n"
            f"📢 Бот будет отправлять сообщения каждые 2 секунды\n"
            f"❌ Для остановки: напишите 'стоп' или `/stop`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "формат времени" in error_msg.lower() or "hh:mm" in error_msg.lower():
            await update.message.reply_text(
                "❌ **Неверный формат времени!**\n\n"
                "📝 **Правильный формат:** `HH:MM`\n\n"
                "**Примеры правильного формата:**\n"
                "• `/repeat 08:30 12345` ✅\n"
                "• `/repeat 8:30 12345` ✅ (можно без ведущего нуля)\n"
                "• `/repeat 23:59 67` ✅\n\n"
                "❌ **Неправильно:**\n"
                "• `/repeat 8-30 12345` ❌ (дефис вместо двоеточия)\n"
                "• `/repeat 830 12345` ❌ (без разделителя)\n"
                "• `/repeat 25:00 12345` ❌ (час больше 23)",
                parse_mode="Markdown"
            )
        elif "дней недели" in error_msg.lower():
            await update.message.reply_text(
                "❌ **Неверный формат дней!**\n\n"
                "Используйте числа от **1** до **7**:\n"
                "• 1 = Понедельник\n"
                "• 2 = Вторник\n"
                "• 3 = Среда\n"
                "• 4 = Четверг\n"
                "• 5 = Пятница\n"
                "• 6 = Суббота\n"
                "• 7 = Воскресенье\n\n"
                "**Примеры:**\n"
                "• `/repeat 08:30 12345` - будни (Пн-Пт)\n"
                "• `/repeat 09:00 1234567` - каждый день\n"
                "• `/repeat 12:00 67` - выходные",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка: {error_msg}\n\n"
                "Используйте: `/repeat HH:MM дни [сообщение]`\n"
                "Пример: `/repeat 08:30 12345 Работа`",
                parse_mode="Markdown"
            )

# Обработчик команды /stop
async def stop_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Останавливает все будильники"""
    user_id = update.effective_user.id
    
    if user_id not in active_alarms or not active_alarms[user_id]:
        await update.message.reply_text("⏸ Вы не установили ни одного будильника.")
        return
    
    # Останавливаем спам
    spam_active[user_id] = False
    
    # Отменяем все задачи
    for task in active_alarms[user_id]:
        task.cancel()
    
    # Получаем повторяющиеся будильники из БД перед удалением
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('SELECT alarm_time, message, repeat_days FROM alarms WHERE user_id = ? AND repeat_days IS NOT NULL AND repeat_days != ""', (user_id,))
    recurring_alarms = cursor.fetchall()
    
    # Удаляем из БД только одноразовые будильники
    cursor.execute('DELETE FROM alarms WHERE user_id = ? AND (repeat_days IS NULL OR repeat_days = "")', (user_id,))
    conn.commit()
    conn.close()
    
    active_alarms[user_id] = []
    
    # Перепланируем повторяющиеся будильники
    for alarm_time, message, repeat_days in recurring_alarms:
        try:
            alarm_datetime = datetime.strptime(alarm_time, "%H:%M")
            repeat_days_set = set(json.loads(repeat_days)) if repeat_days else None
            await schedule_alarm(context.application, user_id, alarm_datetime, message or "", repeat_days_set)
        except Exception as e:
            logger.error(f"Ошибка при перепланировании повторяющегося будильника: {e}")
    
    keyboard = [
        [InlineKeyboardButton("⏰ Установить новый", callback_data="set_alarm")],
        [InlineKeyboardButton("📊 Статус", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if recurring_alarms:
        await update.message.reply_text(
            "🛑 **Одноразовые будильники остановлены!**\n\n"
            "🔄 **Повторяющиеся будильники сохранены и продолжат работу.**\n\n"
            "Для установки нового будильника используйте `/set HH:MM`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🛑 **Все будильники остановлены!**\n\n"
            "Для установки нового будильника используйте `/set HH:MM`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# Функция форматирования дней недели
def format_days(repeat_days: Optional[str]) -> str:
    """Форматирует дни недели для отображения"""
    if not repeat_days:
        return "Одноразовый"
    
    try:
        days_set = set(json.loads(repeat_days))
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        selected_days = [day_names[i] for i in sorted(days_set)]
        return ", ".join(selected_days)
    except:
        return "Одноразовый"

# Обработчик команды /status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус будильников"""
    user_id = update.effective_user.id
    
    # Проверяем БД
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('SELECT alarm_time, message, repeat_days FROM alarms WHERE user_id = ?', (user_id,))
    alarms = cursor.fetchall()
    conn.close()
    
    if not alarms:
        await update.message.reply_text("📭 У вас нет установленных будильников.")
        return
    
    timezone = get_user_timezone(user_id)
    current_time = get_user_datetime_now(user_id).strftime("%H:%M:%S")
    
    status_text = f"📊 **Ваши активные будильники:**\n\n"
    status_text += f"🌍 **Часовой пояс:** `{timezone}`\n"
    status_text += f"🕐 **Текущее время:** `{current_time}`\n\n"
    
    for alarm_time, message, repeat_days in alarms:
        status_text += f"⏰ `{alarm_time}`"
        if message:
            status_text += f" — *{message}*"
        status_text += f"\n📅 *{format_days(repeat_days)}*\n\n"
    
    await update.message.reply_text(status_text, parse_mode="Markdown")

# Обработчик команды /timezone
async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает часовой пояс пользователя"""
    user_id = update.effective_user.id
    
    if not context.args:
        current_tz = get_user_timezone(user_id)
        current_time = get_user_datetime_now(user_id).strftime("%H:%M:%S")
        
        await update.message.reply_text(
            f"🌍 **Текущий часовой пояс:** `{current_tz}`\n"
            f"🕐 **Текущее время:** `{current_time}`\n\n"
            "📝 **Установить часовой пояс:**\n"
            "`/timezone <название>`\n\n"
            "**Примеры:**\n"
            "• `/timezone Europe/Moscow` - Москва\n"
            "• `/timezone Europe/Kiev` - Киев\n"
            "• `/timezone Asia/Tashkent` - Ташкент\n"
            "• `/timezone America/New_York` - Нью-Йорк\n"
            "• `/timezone Asia/Tokyo` - Токио\n"
            "• `/timezone UTC` - UTC\n\n"
            "💡 Используйте формат IANA Time Zone Database\n"
            "Список: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            parse_mode="Markdown"
        )
        return
    
    timezone_str = context.args[0].strip()
    
    # Проверяем валидность часового пояса
    if set_user_timezone(user_id, timezone_str):
        current_time = get_user_datetime_now(user_id).strftime("%H:%M:%S")
        await update.message.reply_text(
            f"✅ **Часовой пояс установлен!**\n\n"
            f"🌍 **Часовой пояс:** `{timezone_str}`\n"
            f"🕐 **Текущее время:** `{current_time}`\n\n"
            "Теперь все будильники будут работать в вашем часовом поясе!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ **Неверный часовой пояс!**\n\n"
            "Используйте формат IANA Time Zone Database.\n\n"
            "**Примеры:**\n"
            "• `Europe/Moscow`\n"
            "• `Europe/Kiev`\n"
            "• `Asia/Tashkent`\n"
            "• `America/New_York`\n"
            "• `UTC`\n\n"
            "Список всех часовых поясов:\n"
            "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            parse_mode="Markdown"
        )

# Обработчик текстовых сообщений (для команды "стоп")
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения"""
    text = update.message.text.lower().strip()
    
    if text in ["стоп", "stop", "остановить", "stop all"]:
        await stop_alarm(update, context)

# Обработчик кнопок (callback query)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на inline-кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "set_alarm":
        user_id = update.effective_user.id
        timezone = get_user_timezone(user_id)
        current_time = get_user_datetime_now(user_id).strftime("%H:%M")
        
        keyboard = [
            [InlineKeyboardButton("📝 Примеры", callback_data="set_examples")],
            [InlineKeyboardButton("🔄 Повторяющийся", callback_data="repeat_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏰ **Установка одноразового будильника**\n\n"
            f"🌍 **Ваш часовой пояс:** `{timezone}`\n"
            f"🕐 **Текущее время:** `{current_time}`\n\n"
            "📝 **Формат команды:**\n"
            "`/set HH:MM [сообщение]`\n\n"
            "**Примеры:**\n"
            "• `/set 08:30` - будильник на 8:30\n"
            "• `/set 08:30 Доброе утро!` - с сообщением\n"
            "• `/set 14:00 Обед`\n"
            "• `/set 22:00 Время спать`\n\n"
            "💡 **Подсказка:** Время указывается в вашем часовом поясе",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif query.data == "set_examples":
        keyboard = [
            [InlineKeyboardButton("🔄 Повторяющийся", callback_data="repeat_help")],
            [InlineKeyboardButton("◀️ Назад", callback_data="set_alarm")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 **Примеры одноразовых будильников:**\n\n"
            "• `/set 08:30`\n"
            "  → Будильник на 8:30 утра\n\n"
            "• `/set 08:30 Доброе утро!`\n"
            "  → Будильник на 8:30 с сообщением\n\n"
            "• `/set 14:00 Обед`\n"
            "  → Будильник на 14:00 с напоминанием об обеде\n\n"
            "• `/set 22:00 Время спать`\n"
            "  → Будильник на 22:00 с напоминанием\n\n"
            "💡 **Формат:** `/set HH:MM [сообщение]`\n"
            "Время указывается в вашем часовом поясе",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif query.data == "set_help":
        user_id = update.effective_user.id
        timezone = get_user_timezone(user_id)
        current_time = get_user_datetime_now(user_id).strftime("%H:%M")
        
        keyboard = [
            [InlineKeyboardButton("📝 Примеры", callback_data="set_examples")],
            [InlineKeyboardButton("🔄 Повторяющийся", callback_data="repeat_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏰ **Установка одноразового будильника**\n\n"
            f"🌍 **Ваш часовой пояс:** `{timezone}`\n"
            f"🕐 **Текущее время:** `{current_time}`\n\n"
            "📝 **Формат команды:**\n"
            "`/set HH:MM [сообщение]`\n\n"
            "**Примеры:**\n"
            "• `/set 08:30` - будильник на 8:30\n"
            "• `/set 08:30 Доброе утро!` - с сообщением\n"
            "• `/set 14:00 Обед`\n"
            "• `/set 22:00 Время спать`\n\n"
            "💡 **Подсказка:** Время указывается в вашем часовом поясе",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif query.data == "repeat_help":
        user_id = update.effective_user.id
        timezone = get_user_timezone(user_id)
        current_time = get_user_datetime_now(user_id).strftime("%H:%M")
        
        keyboard = [
            [InlineKeyboardButton("📝 Примеры", callback_data="repeat_examples")],
            [InlineKeyboardButton("⏰ Одноразовый", callback_data="set_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔄 **Установка повторяющегося будильника**\n\n"
            f"🌍 **Ваш часовой пояс:** `{timezone}`\n"
            f"🕐 **Текущее время:** `{current_time}`\n\n"
            "📝 **Формат команды:**\n"
            "`/repeat HH:MM дни [сообщение]`\n\n"
            "📅 **Формат дней (1-7):**\n"
            "• `1` = Понедельник\n"
            "• `2` = Вторник\n"
            "• `3` = Среда\n"
            "• `4` = Четверг\n"
            "• `5` = Пятница\n"
            "• `6` = Суббота\n"
            "• `7` = Воскресенье\n\n"
            "**Примеры:**\n"
            "• `/repeat 08:30 12345` - будни (Пн-Пт)\n"
            "• `/repeat 09:00 1234567` - каждый день\n"
            "• `/repeat 12:00 67` - выходные (Сб-Вс)\n"
            "• `/repeat 08:00 12345 Работа` - будни с сообщением\n\n"
            "💡 **Подсказка:** Время указывается в вашем часовом поясе",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif query.data == "repeat_examples":
        keyboard = [
            [InlineKeyboardButton("⏰ Одноразовый", callback_data="set_help")],
            [InlineKeyboardButton("◀️ Назад", callback_data="repeat_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 **Примеры повторяющихся будильников:**\n\n"
            "• `/repeat 08:30 12345`\n"
            "  → Будни (Пн-Пт) в 8:30\n\n"
            "• `/repeat 09:00 1234567`\n"
            "  → Каждый день в 9:00\n\n"
            "• `/repeat 12:00 67`\n"
            "  → Выходные (Сб-Вс) в 12:00\n\n"
            "• `/repeat 08:00 12345 Работа`\n"
            "  → Будни в 8:00 с сообщением\n\n"
            "• `/repeat 22:00 67 Отдых`\n"
            "  → Выходные в 22:00 с сообщением\n\n"
            "💡 **Формат:** `/repeat HH:MM дни [сообщение]`\n"
            "Время указывается в вашем часовом поясе",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif query.data == "status":
        user_id = update.effective_user.id
        
        # Проверяем БД
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        cursor.execute('SELECT alarm_time, message, repeat_days FROM alarms WHERE user_id = ?', (user_id,))
        alarms = cursor.fetchall()
        conn.close()
        
        if not alarms:
            await query.edit_message_text(
                "📭 **Нет активных будильников**\n\n"
                "Используйте `/set HH:MM` для одноразового будильника\n"
                "Или `/repeat HH:MM дни` для повторяющегося",
                parse_mode="Markdown"
            )
        else:
            timezone = get_user_timezone(user_id)
            current_time = get_user_datetime_now(user_id).strftime("%H:%M:%S")
            
            status_text = "📊 **Ваши активные будильники:**\n\n"
            status_text += f"🌍 **Часовой пояс:** `{timezone}`\n"
            status_text += f"🕐 **Текущее время:** `{current_time}`\n\n"
            
            for alarm_time, message, repeat_days in alarms:
                status_text += f"⏰ `{alarm_time}`"
                if message:
                    status_text += f" — *{message}*"
                status_text += f"\n📅 *{format_days(repeat_days)}*\n\n"
            
            await query.edit_message_text(
                status_text,
                parse_mode="Markdown"
            )
    elif query.data == "stop":
        user_id = update.effective_user.id
        
        if user_id not in active_alarms or not active_alarms[user_id]:
            await query.edit_message_text(
                "⏸ **Нет активных будильников**\n\n"
                "Используйте `/set HH:MM` для установки",
                parse_mode="Markdown"
            )
            return
        
        # Останавливаем спам
        spam_active[user_id] = False
        
        # Отменяем все задачи
        for task in active_alarms[user_id]:
            task.cancel()
        
        # Получаем повторяющиеся будильники из БД перед удалением
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        cursor.execute('SELECT alarm_time, message, repeat_days FROM alarms WHERE user_id = ? AND repeat_days IS NOT NULL AND repeat_days != ""', (user_id,))
        recurring_alarms = cursor.fetchall()
        
        # Удаляем из БД только одноразовые будильники
        cursor.execute('DELETE FROM alarms WHERE user_id = ? AND (repeat_days IS NULL OR repeat_days = "")', (user_id,))
        conn.commit()
        conn.close()
        
        active_alarms[user_id] = []
        
        # Перепланируем повторяющиеся будильники
        for alarm_time, message, repeat_days in recurring_alarms:
            try:
                alarm_datetime = datetime.strptime(alarm_time, "%H:%M")
                repeat_days_set = set(json.loads(repeat_days)) if repeat_days else None
                await schedule_alarm(context.application, user_id, alarm_datetime, message or "", repeat_days_set)
            except Exception as e:
                logger.error(f"Ошибка при перепланировании повторяющегося будильника: {e}")
        
        if recurring_alarms:
            await query.edit_message_text(
                "🛑 **Одноразовые будильники остановлены!**\n\n"
                "🔄 **Повторяющиеся будильники сохранены и продолжат работу.**\n\n"
                "Для установки нового будильника отправьте `/set HH:MM`",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "🛑 **Все будильники остановлены!**\n\n"
                "Для установки нового будильника отправьте `/set HH:MM`",
                parse_mode="Markdown"
            )

def main():
    """Основная функция запуска бота"""
    # Инициализация БД
    init_db()
    
    # Получаем токен из переменной окружения
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        print("\n❌ ОШИБКА: Необходимо установить TELEGRAM_BOT_TOKEN")
        print("\nСоздайте файл .env и добавьте:")
        print("TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather")
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_alarm))
    application.add_handler(CommandHandler("repeat", set_repeat_alarm))
    application.add_handler(CommandHandler("stop", stop_alarm))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("timezone", set_timezone))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Обработчик для inline-кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()

