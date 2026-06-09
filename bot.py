from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from datetime import datetime, time
import pytz
import requests
import sqlite3

TOKEN = "8809093169:AAGAgYGALY48AaChT07oxXwGlwXM4oqSoXU"
KZ_TZ = pytz.timezone("Asia/Almaty")

COOKIES = {
    "r_t": "def502005220000c2755e60840752a60558534749a28546f2bb4f80fbde6ee3e4ca09d28d8133aa9ba9d16aed2817a7b9309b5d6195ed1983b490d7a360cbe5c123c2fdf43e8f3c397acd05434aeb52086c24e7776e7b4fbd4b298f98c0bcda56dd0069c25a49bcbbb4be42e713994c43deb68f8ee97dfeb8526e0a663f7788c339cd3d452e9209cac72b31cfe08f02e0662cf47cc82546fb8b3b608a79841dbe6a594e42ebe85b3732b5e860e6185600b27ee74a09235529d6329e9105a96041d866eb8a04a0c89a20aa01635a7728683f6650179f1da7696",
    "schoolId": "1012792",
    "userId": "95035352",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.8809093169:AAGAgYGALY48AaChT07oxXwGlwXM4oqSoXU0.0",
    "Referer": "https://www.bilimclass.kz/",
    "Accept": "application/json",


# База данных
def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            subscribed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def toggle_subscription(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT subscribed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        new_val = 0 if row[0] else 1
        c.execute("UPDATE users SET subscribed = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        conn.close()
        return new_val
    conn.close()
    return 0

def get_subscribed_users():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE subscribed = 1")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def is_subscribed(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT subscribed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

lesson_times = [
    ("08:00", "08:45"),
    ("08:55", "09:40"),
    ("09:55", "10:40"),
    ("10:55", "11:40"),
    ("11:50", "12:35"),
    ("12:50", "13:35"),
    ("13:45", "14:30"),
    ("14:40", "15:25"),
    ("15:35", "16:20"),
]

schedule = {
    "Понедельник": [
        "Классный час", "Химия", "Биология", "Информатика",
        "Казахский язык и литература", "Русский язык",
        "Английский язык", "Физика", "Светскость и основы религиоведения"
    ],
    "Вторник": [
        "Физическая культура", "История Казахстана", "Основы права", "Алгебра",
        "Казахский язык и литература", "Английский язык",
        "Русская литература", "Комплексная психологическая программа"
    ],
    "Среда": [
        "Английский язык", "География", "Химия", "Экология здоровья человека",
        "Физическая культура", "Казахский язык и литература",
        "Русский язык", "Through the Pages of Literary Works"
    ],
    "Четверг": [
        "География", "Биология", "Физика", "Геометрия",
        "Русская литература", "Алгебра",
        "Физическая культура", "Deutsche Grammatik"
    ],
    "Пятница": [
        "История Казахстана", "Алгебра", "Казахский язык и литература",
        "Русская литература", "Геометрия",
        "Всемирная история", "Художественный труд"
    ]
}

days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]

def get_main_keyboard():
    keyboard = [
        ["📅 Сегодня", "⏭️ Завтра"],
        ["📚 Неделя", "⏰ Сейчас"],
        ["📆 Выбрать день", "🔔 Уведомления"],
        ["📊 Оценки", "ℹ️ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def format_schedule(day):
    lessons = schedule[day]
    text = "📅 " + day + "\n\n"
    for i, lesson in enumerate(lessons):
        if i < len(lesson_times):
            start, end = lesson_times[i]
            text += start + "-" + end + " " + str(i+1) + ". " + lesson + "\n"
        else:
            text += str(i+1) + ". " + lesson + "\n"
    return text

def get_current_lesson(day):
    now = datetime.now(KZ_TZ)
    current_time = now.strftime("%H:%M")
    lessons = schedule.get(day, [])
    for i, (start, end) in enumerate(lesson_times):
        if start <= current_time <= end:
            if i < len(lessons):
                return "Сейчас идет:\n" + str(i+1) + ". " + lessons[i] + "\n" + start + " - " + end
    for i, (start, end) in enumerate(lesson_times):
        if current_time < start:
            if i < len(lessons):
                return "Следующий урок:\n" + str(i+1) + ". " + lessons[i] + "\n" + start + " - " + end
    return "Уроки на сегодня закончились!"

def get_grades():
    try:
        url = "https://api.bilimclass.kz/api/v4/os/clientoffice/diary/quarter"
        params = {
            "schoolId": "1012792",
            "year": "2025",
            "period": "1",
            "periodType": "quarter",
            "groupId": "110110"
        }
        response = requests.get(url, params=params, cookies=COOKIES, headers=HEADERS)
        data = response.json()
        subjects = data.get("data", [])
        if not subjects:
            return "Оценок пока нет"
        text = "Оценки за 1 четверть:\n\n"
        for subject in subjects:
            name = subject.get("subjectName", "Неизвестно")
            grade = subject.get("finalScore") or "-"
            text += str(name) + ": " + str(grade) + "\n"
        return text
    except Exception as e:
        return "Ошибка загрузки оценок: " + str(e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id, user.username or user.first_name)
    await update.message.reply_text(
        "Привет " + (user.first_name or "!") + "! Я школьный бот. Показываю расписание и оценки",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Доступные функции:\n\n"
        "Сегодня - расписание на сегодня\n"
        "Завтра - расписание на завтра\n"
        "Неделя - все расписание\n"
        "Сейчас - какой урок идет\n"
        "Выбрать день - любой день недели\n"
        "Оценки - оценки за четверть\n"
        "Уведомления - рассылка утром в 7:00",
        reply_markup=get_main_keyboard()
    )

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weekday = datetime.now(KZ_TZ).weekday()
    if weekday > 4:
        await update.message.reply_text("Сегодня выходной!")
        return
    await update.message.reply_text(format_schedule(days[weekday]))

async def tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weekday = datetime.now(KZ_TZ).weekday() + 1
    if weekday > 4:
        await update.message.reply_text("Завтра выходной!")
        return
    await update.message.reply_text(format_schedule(days[weekday]))

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for day in days:
        await update.message.reply_text(format_schedule(day))

async def current_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weekday = datetime.now(KZ_TZ).weekday()
    if weekday > 4:
        await update.message.reply_text("Сегодня выходной!")
        return
    result = get_current_lesson(days[weekday])
    await update.message.reply_text(result)

async def grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Загружаю оценки...")
    text = get_grades()
    await update.message.reply_text(text)

async def choose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(day, callback_data="day_" + day)] for day in days]
    await update.message.reply_text("Выбери день:", reply_markup=InlineKeyboardMarkup(keyboard))

async def day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day = query.data.replace("day_", "")
    await query.message.reply_text(format_schedule(day))

async def notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    add_user(user.id, user.username or user.first_name)
    result = toggle_subscription(user.id)
    if result:
        await update.message.reply_text("Уведомления включены! Буду писать в 7:00")
    else:
        await update.message.reply_text("Уведомления отключены")

async def morning_notification(context: ContextTypes.DEFAULT_TYPE):
    weekday = datetime.now(KZ_TZ).weekday()
    if weekday > 4:
        return
    text = "Доброе утро!\n\n" + format_schedule(days[weekday])
    for user_id in get_subscribed_users():
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
        except Exception:
            pass

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    handlers = {
        "📅 Сегодня": today,
        "⏭️ Завтра": tomorrow,
        "📚 Неделя": week,
        "⏰ Сейчас": current_lesson,
        "📆 Выбрать день": choose_day,
        "📊 Оценки": grades,
        "🔔 Уведомления": notifications,
        "ℹ️ Помощь": help_command,
    }
    handler = handlers.get(text)
    if handler:
        await handler(update, context)

init_db()

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("today", today))
app.add_handler(CommandHandler("tomorrow", tomorrow))
app.add_handler(CommandHandler("week", week))
app.add_handler(CommandHandler("now", current_lesson))
app.add_handler(CommandHandler("grades", grades))
app.add_handler(CallbackQueryHandler(day_callback, pattern="^day_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buttons))

app.job_queue.run_daily(
    morning_notification,
    time=time(hour=7, minute=0, tzinfo=KZ_TZ)
)

print("Бот запущен...")
app.run_polling()
