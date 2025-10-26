import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List
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
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Загрузка сохраненных будильников из БД
async def load_saved_alarms(app: Application):
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, alarm_time, message FROM alarms')
    alarms = cursor.fetchall()
    conn.close()
    
    for user_id, alarm_time, message in alarms:
        try:
            alarm_datetime = datetime.strptime(alarm_time, "%H:%M")
            await schedule_alarm(app, user_id, alarm_datetime, message or "")
        except Exception as e:
            logger.error(f"Ошибка при загрузке будильника: {e}")

# Функция планирования будильника
async def schedule_alarm(app: Application, user_id: int, alarm_time: datetime, message: str = ""):
    """Планирует будильник на указанное время"""
    now = datetime.now()
    target = alarm_time.replace(year=now.year, month=now.month, day=now.day)
    
    # Если время прошло, планируем на завтра
    if target < now:
        target = target.replace(day=target.day + 1)
    
    delay = (target - now).total_seconds()
    logger.info(f"Будильник запланирован для пользователя {user_id} на {alarm_time.strftime('%H:%M')}")
    
    # Создаем задачу
    task = asyncio.create_task(
        send_alarm(app, user_id, alarm_time, message, delay)
    )
    
    # Сохраняем задачу
    if user_id not in active_alarms:
        active_alarms[user_id] = []
    active_alarms[user_id].append(task)

# Функция отправки спам-сообщений
async def spam_messages(app: Application, user_id: int, alarm_time: datetime, message: str):
    """Отправляет спам-сообщения каждые 2 секунды пока флаг активен"""
    spam_active[user_id] = True
    
    while spam_active.get(user_id, False):
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
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
async def send_alarm(app: Application, user_id: int, alarm_time: datetime, message: str, delay: float):
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
        
    except asyncio.CancelledError:
        logger.info(f"Будильник отменен для пользователя {user_id}")
        spam_active[user_id] = False
    except Exception as e:
        logger.error(f"Ошибка при отправке будильника: {e}")

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    keyboard = [
        [InlineKeyboardButton("⏰ Установить будильник", callback_data="set_alarm")],
        [InlineKeyboardButton("📊 Мои будильники", callback_data="status")],
        [InlineKeyboardButton("🛑 Остановить все", callback_data="stop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Привет! Я **Будильник** 📢\n\n"
        "🎯 **Как это работает:**\n"
        "1. Установите время будильника\n"
        "2. Бот будет звонить каждые 5 секунд\n"
        "3. Напишите 'стоп' чтобы остановить\n\n"
        "📌 **Пример:**\n"
        "`/set 08:30 Доброе утро!`\n\n"
        "Или используйте кнопки ниже 👇",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Обработчик команды /set
async def set_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает будильник"""
    if not context.args:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте: /set HH:MM [сообщение]\n"
            "Пример: /set 08:30 Проснись!"
        )
        return
    
    user_id = update.effective_user.id
    
    try:
        # Парсим время
        time_str = context.args[0]
        alarm_time = datetime.strptime(time_str, "%H:%M")
        
        # Получаем сообщение, если есть
        message = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        
        # Отменяем предыдущие будильники для пользователя
        if user_id in active_alarms:
            for task in active_alarms[user_id]:
                task.cancel()
            active_alarms[user_id] = []
        
        # Отменяем флаг спама если был установлен
        spam_active[user_id] = False
        
        # Планируем новый будильник
        await schedule_alarm(context.application, user_id, alarm_time, message)
        
        # Сохраняем в БД
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        # Удаляем старые будильники пользователя
        cursor.execute('DELETE FROM alarms WHERE user_id = ?', (user_id,))
        # Добавляем новый
        cursor.execute(
            'INSERT INTO alarms (user_id, alarm_time, message, created_at) VALUES (?, ?, ?, ?)',
            (user_id, alarm_time.strftime("%H:%M"), message, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        # Вычисляем время до будильника
        now = datetime.now()
        target = alarm_time.replace(year=now.year, month=now.month, day=now.day)
        
        if target < now:
            target = target.replace(day=target.day + 1)
        
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
            f"⏳ **До будильника:** {time_text.strip() or 'менее минуты'}\n\n"
            f"📢 Бот будет отправлять сообщения каждые 5 секунд\n"
            f"❌ Для остановки: напишите 'стоп' или `/stop`\n\n"
            f"💡 *Или используйте кнопки ниже*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени. Используйте: /set HH:MM [сообщение]\n"
            "Пример: /set 08:30"
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
    
    # Удаляем из БД
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM alarms WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    active_alarms[user_id] = []
    
    keyboard = [
        [InlineKeyboardButton("⏰ Установить новый", callback_data="set_alarm")],
        [InlineKeyboardButton("📊 Статус", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛑 **Все будильники остановлены!**\n\n"
        "Для установки нового будильника используйте `/set HH:MM`",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Обработчик команды /status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус будильников"""
    user_id = update.effective_user.id
    
    # Проверяем БД
    conn = sqlite3.connect('alarms.db')
    cursor = conn.cursor()
    cursor.execute('SELECT alarm_time, message FROM alarms WHERE user_id = ?', (user_id,))
    alarms = cursor.fetchall()
    conn.close()
    
    if not alarms:
        await update.message.reply_text("📭 У вас нет установленных будильников.")
        return
    
    status_text = "📊 Ваши активные будильники:\n\n"
    for alarm_time, message in alarms:
        status_text += f"⏰ {alarm_time}"
        if message:
            status_text += f" — {message}"
        status_text += "\n"
    
    await update.message.reply_text(status_text)

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
        await query.edit_message_text(
            "⏰ **Установить будильник**\n\n"
            "📝 **Формат:**\n"
            "`/set HH:MM [сообщение]`\n\n"
            "**Примеры:**\n"
            "• `/set 08:30 Доброе утро!`\n"
            "• `/set 14:00 Обеденный перерыв`\n"
            "• `/set 22:00 Время спать`\n\n"
            "💡 После установки бот будет звонить каждые 2 секунды",
            parse_mode="Markdown"
        )
    elif query.data == "status":
        user_id = update.effective_user.id
        
        # Проверяем БД
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        cursor.execute('SELECT alarm_time, message FROM alarms WHERE user_id = ?', (user_id,))
        alarms = cursor.fetchall()
        conn.close()
        
        if not alarms:
            await query.edit_message_text(
                "📭 **Нет активных будильников**\n\n"
                "Используйте `/set HH:MM` для установки будильника",
                parse_mode="Markdown"
            )
        else:
            status_text = "📊 **Ваши активные будильники:**\n\n"
            for alarm_time, message in alarms:
                status_text += f"⏰ `{alarm_time}`"
                if message:
                    status_text += f" — *{message}*"
                status_text += "\n"
            
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
        
        # Удаляем из БД
        conn = sqlite3.connect('alarms.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM alarms WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        active_alarms[user_id] = []
        
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
    application.add_handler(CommandHandler("stop", stop_alarm))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Обработчик для inline-кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()

