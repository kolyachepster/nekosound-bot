# ============================================================
#  NekoSound Studio — Telegram Bot
#  Заказы озвучки + предложения проектов
# ============================================================

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

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
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
FIREBASE_KEY = os.getenv('FIREBASE_KEY', 'firebase-key.json')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
#  FIREBASE
# ============================================================
import json

try:
    FIREBASE_KEY_JSON = os.getenv('FIREBASE_KEY_JSON')
    if FIREBASE_KEY_JSON:
          
        cred = credentials.Certificate(json.loads(FIREBASE_KEY_JSON))
    else:
        
        cred = credentials.Certificate(FIREBASE_KEY)
    
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info('✅ Firebase подключён')
except Exception as e:
    logger.error(f'❌ Ошибка Firebase: {e}')
    db = None

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙 Заказать озвучку", callback_data="order")],
        [InlineKeyboardButton("💡 Предложить проект", callback_data="suggest")],
        [InlineKeyboardButton("💰 Прайс-лист", callback_data="price")],
        [InlineKeyboardButton("📞 Связаться", callback_data="contact")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
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
    user = update.effective_user
    args = context.args

    # Проверяем, есть ли deep link (order_ID)
    if args and args[0].startswith('order_'):
        order_id = args[0].replace('order_', '')
        await show_order_from_site(update, context, order_id)
        return

    welcome = (
        f"Привет, {user.first_name}! 🐱🎙️\n\n"
        f"Я бот студии <b>NekoSound Studio</b>.\n"
        f"Здесь вы можете заказать озвучку или предложить проект.\n\n"
        f"Выберите действие:"
    )

    await update.message.reply_text(
        welcome,
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )

# ============================================================
#  ПОКАЗ ЗАКАЗА С САЙТА
# ============================================================
async def show_order_from_site(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str):
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

        # Сохраняем order_id в контексте
        context.user_data['order_id'] = order_id
        context.user_data['state'] = 'awaiting_confirm'

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

    # ─── Главное меню ───
    if data == "order":
        await query.edit_message_text(
            "🎙 <b>Заказ озвучки</b>\n\n"
            "Пожалуйста, заполните форму одним сообщением:\n\n"
            "1️⃣ Название проекта\n"
            "2️⃣ Тип (аниме/сериал/фильм)\n"
            "3️⃣ Количество серий\n"
            "4️⃣ Ссылка на проект\n"
            "5️⃣ Ваши пожелания\n\n"
            "Пример:\n"
            "<code>Атака Титанов\nАниме\n25\nhttps://...\nХочу с русской озвучкой</code>",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        context.user_data['state'] = 'ordering'

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
        context.user_data['state'] = 'suggesting'

    elif data == "price":
        await query.edit_message_text(
            "💰 <b>Прайс-лист</b>\n\n"
            "• Аниме (12 серий) — от 5 000 ₽\n"
            "• Сериал (1 сезон) — от 7 000 ₽\n"
            "• Фильм — от 3 000 ₽\n"
            "• Мультфильм — от 2 500 ₽\n\n"
            "Точная цена обсуждается индивидуально.",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

    elif data == "contact":
        await query.edit_message_text(
            "📞 <b>Связаться с нами</b>\n\n"
            "Telegram: @nekosoundstudio\n"
            "TikTok: @nekosound_studio\n"
            "Email: nekosoundstudio@gmail.com",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

    elif data == "help":
        await query.edit_message_text(
            "❓ <b>Помощь</b>\n\n"
            "• Нажмите «Заказать озвучку» — чтобы оформить платный заказ\n"
            "• Нажмите «Предложить проект» — чтобы бесплатно предложить аниме/сериал\n"
            "• Нажмите «Прайс-лист» — чтобы узнать цены\n\n"
            "По всем вопросам: @nekosoundstudio",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

    elif data == "cancel":
        context.user_data['state'] = None
        await query.edit_message_text(
            "❌ Действие отменено.",
            reply_markup=main_menu_keyboard()
        )

    # ─── Подтверждение заказа ───
    elif data.startswith("confirm_"):
        order_id = data.replace("confirm_", "")
        await confirm_order(query, context, order_id)

    elif data.startswith("cancel_"):
        order_id = data.replace("cancel_", "")
        await cancel_order(query, order_id)

    elif data.startswith("edit_"):
        order_id = data.replace("edit_", "")
        await query.edit_message_text(
            "✏️ Отправьте исправленные данные одним сообщением:\n\n"
            "Пример:\n"
            "<code>Новое название\nАниме\n12\nhttps://...\nКомментарий</code>",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        context.user_data['state'] = 'editing'
        context.user_data['edit_order_id'] = order_id

# ============================================================
#  ПОДТВЕРЖДЕНИЕ ЗАКАЗА
# ============================================================
async def confirm_order(query, context, order_id):
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

        # Уведомление админам
        order_doc = order_ref.get()
        order = order_doc.to_dict()

        admin_text = (
            f"🎙 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
            f"👤 От: {query.from_user.first_name} "
            f"(@{query.from_user.username or 'нет'})\n"
            f"🆔 ID: <code>{query.from_user.id}</code>\n\n"
            f"📌 Название: {order.get('title', '—')}\n"
            f"🎭 Тип: {order.get('type', '—')}\n"
            f"💰 Цена: {order.get('price', '—')}"
        )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.warning(f'Не удалось уведомить админа {admin_id}: {e}')

        await query.edit_message_text(
            "✅ <b>Спасибо! Заказ подтверждён.</b>\n\n"
            "Мы свяжемся с вами в ближайшее время для уточнения деталей.",
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f'Ошибка подтверждения: {e}')
        await query.edit_message_text("❌ Ошибка подтверждения заказа.")

# ============================================================
#  ОТМЕНА ЗАКАЗА
# ============================================================
async def cancel_order(query, order_id):
    if not db:
        await query.edit_message_text("❌ База данных недоступна.")
        return

    try:
        db.collection('orders').document(order_id).update({
            'status': 'cancelled',
            'cancelledAt': firestore.SERVER_TIMESTAMP
        })

        await query.edit_message_text(
            "❌ Заказ отменён.\n\n"
            "Если хотите создать новый — используйте /start",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f'Ошибка отмены: {e}')
        await query.edit_message_text("❌ Ошибка отмены заказа.")

# ============================================================
#  ТЕКСТОВЫЕ СООБЩЕНИЯ
# ============================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    state = context.user_data.get('state')

    if state == 'ordering':
        await process_order(update, context, user, text)
    elif state == 'suggesting':
        await process_suggestion(update, context, user, text)
    elif state == 'editing':
        await process_edit(update, context, user, text)
    else:
        await update.message.reply_text(
            "Используйте /start для начала работы.",
            reply_markup=main_menu_keyboard()
        )

# ============================================================
#  ОБРАБОТКА ЗАКАЗА
# ============================================================
async def process_order(update, context, user, text):
    if not db:
        await update.message.reply_text("❌ База данных недоступна.")
        return

    # Отправляем админам
    admin_text = (
        f"🎙 <b>НОВЫЙ ЗАКАЗ</b> (из бота)\n\n"
        f"👤 От: {user.first_name} (@{user.username or 'нет'})\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"📝 <b>Текст:</b>\n{text}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.warning(f'Не удалось уведомить админа {admin_id}: {e}')

    # Сохраняем в Firestore
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

    context.user_data['state'] = None

    await update.message.reply_text(
        "✅ <b>Спасибо! Ваш заказ отправлен.</b>\n\n"
        "Мы свяжемся с вами в ближайшее время.",
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )

# ============================================================
#  ОБРАБОТКА ПРЕДЛОЖЕНИЯ
# ============================================================
async def process_suggestion(update, context, user, text):
    if not db:
        await update.message.reply_text("❌ База данных недоступна.")
        return

    admin_text = (
        f"💡 <b>НОВОЕ ПРЕДЛОЖЕНИЕ</b> (из бота)\n\n"
        f"👤 От: {user.first_name} (@{user.username or 'нет'})\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"📝 <b>Текст:</b>\n{text}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.warning(f'Не удалось уведомить админа {admin_id}: {e}')

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

    context.user_data['state'] = None

    await update.message.reply_text(
        "✅ <b>Спасибо! Ваше предложение отправлено.</b>\n\n"
        "Мы рассмотрим его и свяжемся с вами.",
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )

# ============================================================
#  ОБРАБОТКА РЕДАКТИРОВАНИЯ
# ============================================================
async def process_edit(update, context, user, text):
    if not db:
        await update.message.reply_text("❌ База данных недоступна.")
        return

    order_id = context.user_data.get('edit_order_id')
    if not order_id:
        await update.message.reply_text("❌ Ошибка: заказ не найден.")
        return

    try:
        lines = text.strip().split('\n')
        update_data = {
            'title': lines[0] if len(lines) > 0 else '',
            'type': lines[1] if len(lines) > 1 else '',
            'episodes': lines[2] if len(lines) > 2 else '',
            'link': lines[3] if len(lines) > 3 else '',
            'notes': lines[4] if len(lines) > 4 else '',
            'updatedAt': firestore.SERVER_TIMESTAMP
        }

        db.collection('orders').document(order_id).update(update_data)

        context.user_data['state'] = None
        context.user_data['edit_order_id'] = None

        await update.message.reply_text(
            "✅ Заказ обновлён!",
            reply_markup=main_menu_keyboard()
        )

        await show_order_from_site(update, context, order_id)

    except Exception as e:
        logger.error(f'Ошибка редактирования: {e}')
        await update.message.reply_text("❌ Ошибка редактирования.")

# ============================================================
#  КОМАНДЫ АДМИНА
# ============================================================
async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа.")
        return

    if not db:
        await update.message.reply_text("❌ База данных недоступна.")
        return

    try:
        orders = db.collection('orders') \
            .where('status', '==', 'confirmed') \
            .order_by('confirmedAt', direction=firestore.Query.DESCENDING) \
            .limit(10).stream()

        text = "📋 <b>Последние заказы:</b>\n\n"
        count = 0
        for o in orders:
            data = o.to_dict()
            text += (
                f"• <b>{data.get('title', '—')}</b>\n"
                f"  {data.get('type', '—')} · {data.get('price', '—')}\n"
                f"  ID: <code>{o.id}</code>\n\n"
            )
            count += 1

        if count == 0:
            text = "📋 Заказов пока нет."

        await update.message.reply_text(text, parse_mode='HTML')

    except Exception as e:
        logger.error(f'Ошибка админ-команды: {e}')
        await update.message.reply_text("❌ Ошибка загрузки заказов.")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа.")
        return

    if not db:
        await update.message.reply_text("❌ База данных недоступна.")
        return

    try:
        orders_count = len(list(db.collection('orders').stream()))
        suggestions_count = len(list(db.collection('suggestions').stream()))
        users_count = len(list(db.collection('users').stream()))

        text = (
            f"📊 <b>Статистика</b>\n\n"
            f"🎙 Заказов: {orders_count}\n"
            f"💡 Предложений: {suggestions_count}\n"
            f"👥 Пользователей: {users_count}"
        )

        await update.message.reply_text(text, parse_mode='HTML')

    except Exception as e:
        logger.error(f'Ошибка статистики: {e}')
        await update.message.reply_text("❌ Ошибка загрузки статистики.")

# ============================================================
#  ЗАПУСК
# ============================================================
def main():
    if not BOT_TOKEN:
        logger.error('❌ BOT_TOKEN не указан в .env')
        return

    logger.info('🚀 Запуск бота...')
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", admin_orders))
    app.add_handler(CommandHandler("stats", admin_stats))

    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info('✅ Бот запущен!')
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()