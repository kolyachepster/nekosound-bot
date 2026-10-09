import os
import json
import asyncio
import logging
from http.server import BaseHTTPRequestHandler

import firebase_admin
from firebase_admin import credentials, firestore

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ============================================================
#  НАСТРОЙКИ
# ============================================================
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
#  FIREBASE
# ============================================================
_db = None

def get_db():
    global _db
    if _db is not None:
        return _db
    try:
        key = os.getenv('FIREBASE_KEY_JSON')
        if key:
            cred = credentials.Certificate(json.loads(key))
            firebase_admin.initialize_app(cred)
            _db = firestore.client()
            logger.info('✅ Firebase OK')
    except Exception as e:
        logger.error(f'❌ Firebase error: {e}')
    return _db

# ============================================================
#  СОСТОЯНИЯ
# ============================================================
def get_state(uid):
    db = get_db()
    if not db:
        return {}
    try:
        doc = db.collection('botStates').document(str(uid)).get()
        return doc.to_dict() if doc.exists else {}
    except:
        return {}

def set_state(uid, state, extra=None):
    db = get_db()
    if not db:
        return
    try:
        data = {'state': state}
        if extra:
            data.update(extra)
        db.collection('botStates').document(str(uid)).set(data, merge=True)
    except Exception as e:
        logger.error(f'set_state: {e}')

def clear_state(uid):
    db = get_db()
    if not db:
        return
    try:
        db.collection('botStates').document(str(uid)).delete()
    except:
        pass

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙 Заказать озвучку", callback_data="order")],
        [InlineKeyboardButton("💡 Предложить проект", callback_data="suggest")],
        [InlineKeyboardButton("💰 Прайс-лист", callback_data="price")],
        [InlineKeyboardButton("📞 Связаться", callback_data="contact")],
    ])

def cancel_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])

# ============================================================
#  ХЕНДЛЕРЫ
# ============================================================
async def cmd_start(update: Update, context):
    clear_state(update.effective_user.id)
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 🐱🎙️\n\n"
        f"Я бот студии <b>NekoSound Studio</b>.\n"
        f"Выберите действие:",
        reply_markup=main_menu(),
        parse_mode='HTML'
    )

async def cb_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "order":
        set_state(uid, 'ordering')
        await query.edit_message_text(
            "🎙 <b>Заказ озвучки</b>\n\n"
            "Заполните форму одним сообщением:\n\n"
            "1️⃣ Название\n"
            "2️⃣ Тип\n"
            "3️⃣ Серий\n"
            "4️⃣ Ссылка\n"
            "5️⃣ Пожелания",
            reply_markup=cancel_menu(),
            parse_mode='HTML'
        )
    elif data == "suggest":
        set_state(uid, 'suggesting')
        await query.edit_message_text(
            "💡 <b>Предложение проекта</b>\n\n"
            "Расскажите о проекте одним сообщением.",
            reply_markup=cancel_menu(),
            parse_mode='HTML'
        )
    elif data == "price":
        await query.edit_message_text(
            "💰 <b>Прайс-лист</b>\n\n"
            "• Аниме — от 5 000 ₽\n"
            "• Сериал — от 7 000 ₽\n"
            "• Фильм — от 3 000 ₽",
            reply_markup=main_menu(),
            parse_mode='HTML'
        )
    elif data == "contact":
        await query.edit_message_text(
            "📞 Telegram: @nekosoundstudio\n"
            "📧 Email: nekosoundstudio@gmail.com",
            reply_markup=main_menu(),
            parse_mode='HTML'
        )
    elif data == "cancel":
        clear_state(uid)
        await query.edit_message_text("❌ Отменено.", reply_markup=main_menu())

async def msg_handler(update: Update, context):
    user = update.effective_user
    text = update.message.text
    state = get_state(user.id).get('state')

    logger.info(f'User {user.id} state={state}')

    if state == 'ordering':
        admin_text = (
            f"🎙 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
            f"👤 {user.first_name} (@{user.username or '—'})\n"
            f"🆔 <code>{user.id}</code>\n\n"
            f"{text}"
        )
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=aid, text=admin_text, parse_mode='HTML')
            except Exception as e:
                logger.warning(f'Admin {aid}: {e}')

        db = get_db()
        if db:
            try:
                db.collection('botOrders').add({
                    'userId': user.id,
                    'username': user.username or '',
                    'firstName': user.first_name,
                    'text': text,
                    'type': 'order',
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'status': 'new'
                })
            except Exception as e:
                logger.error(f'Save error: {e}')

        clear_state(user.id)
        await update.message.reply_text("✅ Заказ отправлен!", reply_markup=main_menu())

    elif state == 'suggesting':
        admin_text = (
            f"💡 <b>НОВОЕ ПРЕДЛОЖЕНИЕ</b>\n\n"
            f"👤 {user.first_name} (@{user.username or '—'})\n"
            f"🆔 <code>{user.id}</code>\n\n"
            f"{text}"
        )
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=aid, text=admin_text, parse_mode='HTML')
            except Exception as e:
                logger.warning(f'Admin {aid}: {e}')

        db = get_db()
        if db:
            try:
                db.collection('botSuggestions').add({
                    'userId': user.id,
                    'username': user.username or '',
                    'text': text,
                    'createdAt': firestore.SERVER_TIMESTAMP
                })
            except Exception as e:
                logger.error(f'Save error: {e}')

        clear_state(user.id)
        await update.message.reply_text("✅ Предложение отправлено!", reply_markup=main_menu())

    else:
        await update.message.reply_text("Используйте /start", reply_markup=main_menu())

# ============================================================
#  VERCEL HANDLER
# ============================================================
async def process_update(data):
    if not BOT_TOKEN:
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    
    await app.initialize()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    await app.shutdown()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'NekoSound Bot is running!')

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            
            # ✅ ПРАВИЛЬНЫЙ способ для Vercel
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_update(data))
            loop.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            logger.error(f'Handler error: {e}')
            self.send_response(200)  # ← 200, чтобы Telegram не спамил
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')