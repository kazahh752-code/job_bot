import asyncio
import logging
import os
from threading import Thread

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

from database import Database
from scheduler import start_scheduler
from config import BOT_TOKEN, PORT

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# Conversation states
CHOOSING_SOURCE, ENTERING_QUERY, ENTERING_REGION, ENTERING_SALARY = range(4)

app_flask = Flask(__name__)

@app_flask.route("/")
def index():
    return "Job Bot is running!", 200


# ─── Handlers ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or user.first_name)
    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я слежу за вакансиями на <b>hh.ru</b> и <b>Авито</b> и присылаю уведомления о новых.\n\n"
        "📌 Команды:\n"
        "/add — добавить отслеживание\n"
        "/list — мои подписки\n"
        "/stop — остановить подписку\n"
        "/help — помощь"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>Как пользоваться:</b>\n\n"
        "1️⃣ /add — создать новую подписку на вакансии\n"
        "2️⃣ Выбери площадку: hh.ru или Авито\n"
        "3️⃣ Введи поисковый запрос (например: <i>Python разработчик</i>)\n"
        "4️⃣ Укажи регион (или пропусти)\n"
        "5️⃣ Укажи минимальную зарплату (или пропусти)\n\n"
        "Бот будет проверять новые вакансии каждые <b>30 минут</b> и присылать уведомления.\n\n"
        "/list — посмотреть все подписки\n"
        "/stop — удалить подписку"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def add_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔴 hh.ru", callback_data="source_hh"),
            InlineKeyboardButton("🟡 Авито", callback_data="source_avito"),
        ],
        [InlineKeyboardButton("🔴🟡 Обе площадки", callback_data="source_both")],
    ]
    await update.message.reply_text(
        "📌 Выбери площадку для поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_SOURCE


async def source_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    source_map = {
        "source_hh": "hh",
        "source_avito": "avito",
        "source_both": "both"
    }
    context.user_data["source"] = source_map[query.data]
    await query.edit_message_text("✏️ Введи поисковый запрос (например: <b>Python разработчик</b>):", parse_mode="HTML")
    return ENTERING_QUERY


async def query_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["query"] = update.message.text.strip()
    await update.message.reply_text(
        "🌍 Введи регион поиска (например: <b>Москва</b>) или напиши <b>нет</b> чтобы искать по всей России:",
        parse_mode="HTML"
    )
    return ENTERING_REGION


async def region_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["region"] = None if text.lower() in ("нет", "no", "-") else text
    await update.message.reply_text(
        "💰 Укажи минимальную зарплату (например: <b>80000</b>) или напиши <b>нет</b>:",
        parse_mode="HTML"
    )
    return ENTERING_SALARY


async def salary_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    salary = None
    if text.lower() not in ("нет", "no", "-"):
        try:
            salary = int(text.replace(" ", "").replace("\u202f", ""))
        except ValueError:
            await update.message.reply_text("⚠️ Неверный формат. Введи число или <b>нет</b>:", parse_mode="HTML")
            return ENTERING_SALARY

    user_id = update.effective_user.id
    source = context.user_data["source"]
    search_query = context.user_data["query"]
    region = context.user_data.get("region")

    sub_id = db.add_subscription(user_id, source, search_query, region, salary)

    source_labels = {"hh": "hh.ru", "avito": "Авито", "both": "hh.ru + Авито"}
    text = (
        f"✅ Подписка создана!\n\n"
        f"🔍 Запрос: <b>{search_query}</b>\n"
        f"📌 Площадка: <b>{source_labels[source]}</b>\n"
        f"🌍 Регион: <b>{region or 'Вся Россия'}</b>\n"
        f"💰 Мин. зарплата: <b>{salary or 'не указана'}</b>\n\n"
        f"Буду проверять каждые 30 минут 🕐"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subs = db.get_subscriptions(user_id)
    if not subs:
        await update.message.reply_text("У тебя нет активных подписок. Добавь через /add")
        return

    source_labels = {"hh": "hh.ru", "avito": "Авито", "both": "hh.ru + Авито"}
    text = "📋 <b>Твои подписки:</b>\n\n"
    for s in subs:
        text += (
            f"#{s['id']} — <b>{s['query']}</b>\n"
            f"   📌 {source_labels.get(s['source'], s['source'])}\n"
            f"   🌍 {s['region'] or 'Вся Россия'}\n"
            f"   💰 от {s['salary_from'] or '—'} ₽\n\n"
        )
    text += "Для удаления: /stop"
    await update.message.reply_text(text, parse_mode="HTML")


async def stop_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subs = db.get_subscriptions(user_id)
    if not subs:
        await update.message.reply_text("У тебя нет активных подписок.")
        return

    keyboard = [
        [InlineKeyboardButton(f"#{s['id']} {s['query']}", callback_data=f"del_{s['id']}")]
        for s in subs
    ]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="del_cancel")])
    await update.message.reply_text(
        "Выбери подписку для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "del_cancel":
        await query.edit_message_text("Отменено.")
        return
    sub_id = int(query.data.split("_")[1])
    db.delete_subscription(sub_id, query.from_user.id)
    await query.edit_message_text(f"✅ Подписка #{sub_id} удалена.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_subscription)],
        states={
            CHOOSING_SOURCE: [CallbackQueryHandler(source_chosen, pattern="^source_")],
            ENTERING_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, query_entered)],
            ENTERING_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, region_entered)],
            ENTERING_SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, salary_entered)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("list", list_subscriptions))
    application.add_handler(CommandHandler("stop", stop_subscription))
    application.add_handler(CallbackQueryHandler(delete_subscription, pattern="^del_"))

    # Start scheduler in background
    start_scheduler(application.bot, db, loop)

    application.run_polling(stop_signals=None)


if __name__ == "__main__":
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()

    app_flask.run(host="0.0.0.0", port=PORT)
