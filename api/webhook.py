# ============================================================
#  NekoSound Studio — Telegram Bot (Vercel Webhook)
# ============================================================

import os
import json
import logging
from http.server import BaseHTTPRequestHandler

import firebase_admin
from firebase_admin import credentials, firestore

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

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
db = None

def init_firebase():
    global db
    if db is not None:
        return db
    
    try:
        firebase_json = os.getenv('FIREBASE_KEY_JSON')
        if firebase_json:
            cred = credentials.Certificate(json.loads(firebase_json))
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            logger.info('✅ Firebase подключён')
    except Exception as e:
        logger.error(f'❌ Ошибка Firebase: {e}')
    
    return db

# ============================================================
#  СОСТОЯНИЕ ПОЛЬЗОВАТЕЛЯ (в Firestore)
# ============================================================
def get_state(user_id):
    """Получить состояние пользователя."""
    db = init_firebase()
    if not db:
        return {}
    try:
        doc = db.collection('botStates').document(str(user_id)).get()
        return doc.to_dict() if doc.exists else {}
    except Exception as e:
        logger.error(f'Ошибка get_state: {e}')
        return {}

def set_state(user_id, state, extra=None):
    """Сохранить состояние пользователя."""
    db = init_firebase()
    if not db:
        return
    try:
        data = {'state': state, 'updatedAt': firestore.SERVER_TIMESTAMP}
        if extra:
            data.update(extra)
        db.collection('botStates').document(str(user_id)).set(data, merge=True)
    except Exception as e:
        logger.error(f'Ошибка set_state: {e}')

def clear_state(user_id):
    """Очистить состояние пользователя."""
    db = init_firebase()
    if not db:
        return
    try:
        db.collection('botStates').document(str(user_id)).delete()
    except Exception as e:
        logger.error(f'Ошибка clear_state: {e}')

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙 Заказать озвучку", callback_data="order")],
        [InlineKeyboardButton("💡 Предложить проект", callback_data="suggest")],
        [InlineKeyboardButton("💰 Прайс-лист", callback_data="price")],
        [InlineKeyboardButton("📞 Связаться", callback_data="contact")],
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])

def confirm_keyboard(order_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order_id}")],
        [InlineKeyboardButton("✏️ Изменить", callback_data=f"edit_{order_id}")],
        [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_id}")],
    ])

# ============================================================
#  /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_firebase()
    user = update.effective_user
    args = context.args

    if args and args[0].startswith('order_'):
        order_id = args[0].replace('order_', '')
        await show_order_from_site(update, context, order_id)
        return

    clear_state(user.id)

    welcome = (
        f"Привет, {user.first_name}! 🐱🎙️\n\n"
        f"Я бот студии <b>NekoSound Studio</b>.\n"
        f"Здесь вы можете заказать озвучку или предложить проект.\n\n"
        f"Выберите действие:"
    )

    await update.message.reply_text(welcome, reply_markup=main_menu_keyboard(), parse_mode='HTML')

# ============================================================
#  ПОКАЗ ЗАКАЗА С САЙТА
# ============================================================
async def show_order_from_site(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str):
    db = init_firebase()
    if not db:
        await update.message.reply_text("❌ База данных недоступна.")
        return

    try:
        order_ref = db.collection('orders').document(order_id)
        order_doc = order_ref.get()

        if not order_doc.exists:
            await update.message.reply_text("😿 Заказ не найден.")
            return

        order = order_doc.to_dict()

        text = (
            f"🎙 <b>Ваш заказ</b>\n\n"
            f"📌 <b>Название:</b> {order.get('title', '—')}\n"
            f"🎭 <b>Тип:</b> {order.get('type', '—')}\n"
            f"🎨 <b>Жанр:</b> {order.get('genre', '—')}\n"
            f"📅 <b>Год:</b> {order.get('year', '—')}\n"
            f"📺 <b>Серий:</b> {order.get('episodes', '—')}\n"
            f"⏱ <b>Длительность:</b> {order.get('duration', '—')} мин\n"
            f"⭐ <b>Популярность:</b> {order.get('popularity', '—')}\n"
            f"🎬 <b>Качество:</b> {order.get('quality', '—')}\n"
            f"🔗 <b>Ссылка:</b> {order.get('link', '—')}\n"
            f"📝 <b>Пожелания:</b> {order.get('notes', '—')}\n\n"
            f"💰 <b>Ориент. стоимость:</b> {order.get('price', '—')}\n\n"
            f"Подтвердите заказ:"
        )

        await update.message.reply_text(
            text,
            reply_markup=confirm_keyboard(order_id),
            parse_mode='HTML'
        )
        set_state(update.effective_user.id, 'awaiting_confirm', {'order_id': order_id})

    except Exception as e:
        logger.error(f'Ошибка загрузки заказа: {e}')
        await update.message.reply_text("❌ Ошибка загрузки заказа.")

# ============================================================
#  КНОПКИ
# ============================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "order":
        await query.edit_message_text(
            "🎙 <b>Заказ озвучки</b>\n\n"
            "Заполните форму одним сообщением:\n\n"
            "1️⃣ Название проекта\n"
            "2️⃣ Тип (аниме/сериал/фильм)\n"
            "3️⃣ Количество серий\n"
            "4️⃣ Ссылка на проект\n"
            "5️⃣ Ваши пожелания",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        set_state(user_id, 'ordering')

    elif data == "suggest":
        await query.edit_message_text(
            "💡 <b>Предложение проекта</b>\n\n"
            "Расскажите, какой проект хотите предложить:\n\n"
            "1️⃣ Название\n"
            "2️⃣ Почему именно он?\n"
            "3️⃣ Ссылка (если есть)",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        set_state(user_id, 'suggesting')

    elif data == "price":
        await query.edit_message_text(
            "💰 <b>Прайс-лист</b>\n\n"
            "• Аниме (12 серий) — от 5 000 ₽\n"
            "• Сериал (1 сезон) — от 7 000 ₽\n"
            "• Фильм — от 3 000 ₽\n"
            "• Мультфильм — от 2 500 ₽",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

    elif data == "contact":
        await query.edit_message_text(
            "📞 <b>Связаться с нами</b>\n\n"
            "Telegram: @nekosoundstudio\n"
            "TikTok: @nekosound_studio\n"
            "Email: nekosoftstudio@gmail.com",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

    elif data == "cancel":
        clear_state(user_id)
        await query.edit_message_text("❌ Действие отменено.", reply_markup=main_menu_keyboard())

    elif data.startswith("confirm_"):
        order_id = data.replace("confirm_", "")
        await confirm_order(query, context, order_id)

    elif data.startswith("cancel_"):
        order_id = data.replace("cancel_", "")
        await cancel_order(query, order_id)

    elif data.startswith("edit_"):
        order_id = data.replace("edit_", "")
        await query.edit_message_text(
            "✏️ Отправьте исправленные данные одним сообщением:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        set_state(user_id, 'editing', {'order_id': order_id})

# ============================================================
#  ПОДТВЕРЖДЕНИЕ / ОТМЕНА
# ============================================================
async def confirm_order(query, context, order_id):
    db = init_firebase()
    if not db:
        await query.edit_message_text("❌ База данных недоступна.")
        return

    try:
        order_ref = db.collection('orders').document(order_id)
        order_ref.update({
            'status': 'confirmed',
            'confirmedAt': firestore.SERVER_TIMESTAMP,
            'confirmedBy': query.from_user.id
        })

        order = order_ref.get().to_dict()
        admin_text = (
            f"🎙 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
            f"👤 От: {query.from_user.first_name} (@{query.from_user.username or 'нет'})\n"
            f"🆔 ID: <code>{query.from_user.id}</code>\n\n"
            f"📌 Название: {order.get('title', '—')}\n"
            f"🎭 Тип: {order.get('type', '—')}\n"
            f"💰 Цена: {order.get('price', '—')}"
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_text, parse_mode='HTML')
            except Exception as e:
                logger.warning(f'Не удалось уведомить админа {admin_id}: {e}')

        clear_state(query.from_user.id)
        await query.edit_message_text(
            "✅ <b>Спасибо! Заказ подтверждён.</b>\n\n"
            "Мы свяжемся с вами в ближайшее время.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f'Ошибка подтверждения: {e}')
        await query.edit_message_text("❌ Ошибка подтверждения.")

async def cancel_order(query, order_id):
    db = init_firebase()
    if not db:
        await query.edit_message_text("❌ База данных недоступна.")
        return

    try:
        db.collection('orders').document(order_id).update({
            'status': 'cancelled',
            'cancelledAt': firestore.SERVER_TIMESTAMP
        })
        clear_state(query.from_user.id)
        await query.edit_message_text(
            "❌ Заказ отменён.\n\nИспользуйте /start для нового заказа.",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f'Ошибка отмены: {e}')
        await query.edit_message_text("❌ Ошибка отмены.")

# ============================================================
#  ТЕКСТ
# ============================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = init_firebase()
    user = update.effective_user
    text = update.message.text
    
    # ✅ Читаем состояние из Firestore, а не из context
    state_data = get_state(user.id)
    state = state_data.get('state')

    logger.info(f'User {user.id} state: {state}')

    if state == 'ordering':
        admin_text = (
            f"🎙 <b>НОВЫЙ ЗАКАЗ</b> (из бота)\n\n"
            f"👤 От: {user.first_name} (@{user.username or 'нет'})\n"
            f"🆔 ID: <code>{user.id}</code>\n\n"
            f"📝 <b>Текст:</b>\n{text}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_text, parse_mode='HTML')
            except Exception as e:
                logger.warning(f'Не удалось уведомить: {e}')

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
                logger.error(f'Ошибка сохранения: {e}')

        clear_state(user.id)
        await update.message.reply_text(
            "✅ <b>Спасибо! Заказ отправлен.</b>",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

    elif state == 'suggesting':
        admin_text = (
            f"💡 <b>НОВОЕ ПРЕДЛОЖЕНИЕ</b> (из бота)\n\n"
            f"👤 От: {user.first_name} (@{user.username or 'нет'})\n"
            f"🆔 ID: <code>{user.id}</code>\n\n"
            f"📝 <b>Текст:</b>\n{text}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_text, parse_mode='HTML')
            except Exception as e:
                logger.warning(f'Не удалось уведомить: {e}')

        if db:
            try:
                db.collection('botOrders').add({
                    'userId': user.id,
                    'username': user.username or '',
                    'firstName': user.first_name,
                    'text': text,
                    'type': 'suggestion',
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'status': 'new'
                })
            except Exception as e:
                logger.error(f'Ошибка сохранения: {e}')

        clear_state(user.id)
        await update.message.reply_text(
            "✅ <b>Спасибо! Предложение отправлено.</b>",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

    elif state == 'editing':
        order_id = state_data.get('order_id')
        if db and order_id:
            try:
                lines = text.strip().split('\n')
                db.collection('orders').document(order_id).update({
                    'title': lines[0] if len(lines) > 0 else '',
                    'type': lines[1] if len(lines) > 1 else '',
                    'episodes': lines[2] if len(lines) > 2 else '',
                    'link': lines[3] if len(lines) > 3 else '',
                    'notes': lines[4] if len(lines) > 4 else '',
                    'updatedAt': firestore.SERVER_TIMESTAMP
                })
                clear_state(user.id)
                await update.message.reply_text("✅ Заказ обновлён!", reply_markup=main_menu_keyboard())
            except Exception as e:
                logger.error(f'Ошибка редактирования: {e}')
                await update.message.reply_text("❌ Ошибка редактирования.")

    else:
        await update.message.reply_text("Используйте /start.", reply_markup=main_menu_keyboard())

# ============================================================
#  VERCEL HANDLER
# ============================================================
async def process_update(update_data):
    if not BOT_TOKEN:
        logger.error('BOT_TOKEN не указан')
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await app.initialize()
    update = Update.de_json(update_data, app.bot)
    await app.process_update(update)
    await app.shutdown()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            update_data = json.loads(body)
            
            import asyncio
            asyncio.run(process_update(update_data))
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            logger.error(f'Ошибка обработки: {e}')
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'NekoSound Bot is running!')