from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, PreCheckoutQuery, SuccessfulPayment,
    LabeledPrice
)
from app.vless_generator import vless_manager
from sqlalchemy import select 
import io
import base64
import qrcode
from aiogram.types import BufferedInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from uuid import uuid4
import app.database.requests as rq
import app.keyboard as kb


router = Router()

CHANNEL = "@tectnetbot"
ADMIN_ID = 1411430230
# Для Telegram Stars provider_token не нужен - оставляем пустым
PROVIDER_TOKEN = ""

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📦 Подписка")],
        [KeyboardButton(text="🔑 Мой VPN ключ"), KeyboardButton(text="⭐ Мой баланс")],
        [KeyboardButton(text="👥 Мои реффералы"), KeyboardButton(text="💫 Пополнить баланс")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="👨‍💻 Админка")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

async def _get_subscription_duration(telegram_id: int) -> int:
    """Определяет длительность подписки пользователя в днях"""
    user_profile = await rq.get_user_profile(telegram_id)
    if not user_profile:
        return 0
        
    user = user_profile['user']
    active_subscription = user_profile.get('active_subscription')
    
    if active_subscription and active_subscription.end_date > datetime.utcnow():
        return (active_subscription.end_date - datetime.utcnow()).days
    
    if user and user.expires and user.expires > datetime.utcnow():
        days_left = (user.expires - datetime.utcnow()).days
        return max(1, days_left)
    
    return 0

# ======= ИНТЕГРАЦИЯ TELEGRAM STARS =======

@router.message(F.text == "💫 Пополнить баланс")
async def buy_stars_menu(message: Message):
    user = await rq.get_user(message.from_user.id)
    if not user:
        user = await rq.set_user(message.from_user.id, message.from_user.username)
    
    await message.answer(
        f"💫 <b>Пополнение баланса Stars</b>\n\n"
        f"💰 Ваш текущий баланс: <b>{user.stars_balance} ⭐</b>\n\n"
        "Выберите пакет Stars для пополнения:\n\n"
        "💎 <b>100 Stars</b> - 100 ⭐\n"
        "💎 <b>500 Stars</b> - 500 ⭐\n" 
        "💎 <b>1000 Stars</b> - 1000 ⭐\n"
        "💎 <b>5000 Stars</b> - 5000 ⭐\n\n",
        reply_markup=kb.buy_stars_keyboard()
    )

@router.callback_query(F.data.startswith("stars_"))
async def process_stars_purchase(callback: CallbackQuery):
    """Обработка выбора пакета Stars"""
    stars_map = {
        "stars_100": {"amount": 100},
        "stars_500": {"amount": 500},
        "stars_1000": {"amount": 1000},
        "stars_5000": {"amount": 5000}
    }
    
    package_data = stars_map.get(callback.data)
    if not package_data:
        await callback.answer("❌ Неверный пакет")
        return
    
    amount = package_data["amount"]
    
    user = await rq.get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Создаем инвойс для оплаты в Stars (валюта XTR)
    # Для Stars amount указывается в целых числах (1 Star = 1 единица)
    prices = [LabeledPrice(label=f"Пополнение баланса на {amount} Stars", amount=amount)]
    
    invoice_title = f"Пополнение баланса на {amount} Stars"
    invoice_description = f"Пополнение баланса в VPN боте. После оплаты {amount} Stars будут зачислены на ваш счет."
    invoice_payload = f"stars_{amount}_{user.tg_id}_{uuid4().hex[:8]}"
    
    # Создаем запись о платеже в базе
    payment = await rq.create_payment(user.id, amount, invoice_payload)
    if not payment:
        await callback.answer("❌ Ошибка создания платежа")
        return
    
    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=invoice_title,
            description=invoice_description,
            payload=invoice_payload,
            provider_token=PROVIDER_TOKEN,  # Пустая строка для Stars
            currency="XTR",  # Валюта Telegram Stars
            prices=prices,
            start_parameter="stars-purchase",
            need_email=False,
            need_phone_number=False,
            need_shipping_address=False,
            is_flexible=False,
            max_tip_amount=0,
            suggested_tip_amounts=[]
        )
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка создания счета: {e}")

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Обработка предварительного запроса оплаты"""
    await pre_checkout_query.bot.answer_pre_checkout_query(
        pre_checkout_query_id=pre_checkout_query.id,
        ok=True,
        error_message="Произошла ошибка при обработке платежа. Попробуйте позже."
    )

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Обработка успешного платежа"""
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    
    # Проверяем, что платеж в валюте XTR (Telegram Stars)
    if payment_info.currency != "XTR":
        await message.answer("❌ Неподдерживаемая валюта платежа")
        return
    
    if payload.startswith("stars_"):
        # Обработка пополнения баланса Stars
        parts = payload.split("_")
        if len(parts) >= 3:
            amount = int(parts[1])
            user_tg_id = int(parts[2])
            
            user = await rq.get_user(user_tg_id)
            if user:
                # Находим платеж в базе по payload
                payments = await rq.get_user_payments(user_tg_id)
                target_payment = None
                for payment in payments:
                    if payment.invoice_payload == payload:
                        target_payment = payment
                        break
                
                if target_payment:
                    # Завершаем платеж и начисляем Stars
                    success = await rq.complete_payment(
                        target_payment.id,
                        payment_info.provider_payment_charge_id,
                        payment_info.telegram_payment_charge_id
                    )
                    
                    if success:
                        updated_user = await rq.get_user(user_tg_id)
                        await message.answer(
                            f"🎉 <b>Платеж успешно завершен!</b>\n\n"
                            f"💫 На ваш баланс зачислено: <b>{amount} Stars</b>\n"
                            f"💰 Текущий баланс: <b>{updated_user.stars_balance} ⭐</b>\n\n"
                            f"💳 ID транзакции: {payment_info.telegram_payment_charge_id}\n"
                            f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                            f"Теперь вы можете приобрести подписку в разделе \"📦 Подписка\"",
                            reply_markup=get_main_keyboard(message.from_user.id)
                        )
                    else:
                        await message.answer("❌ Ошибка при обработке платежа")
                else:
                    await message.answer("❌ Платеж не найден в системе")
            else:
                await message.answer("❌ Пользователь не найден")
    else:
        await message.answer("❌ Неизвестный тип платежа")

# ======= ОБРАБОТЧИКИ ПОДПИСКИ =======

@router.message(F.text == "📦 Подписка")
async def subscription(message: Message):
    is_active, status_text = await rq.check_subscription_status(message.from_user.id)
    user = await rq.get_user(message.from_user.id)
    
    subscription_text = "📦 <b>Пакеты подписки VPN</b>\n\n"
    subscription_text += f"🛡️ <b>Текущий статус:</b> {'✅ ' + status_text if is_active else '❌ ' + status_text}\n"
    subscription_text += f"💰 <b>Ваш баланс:</b> {user.stars_balance if user else 0} ⭐\n\n"
    subscription_text += "💎 <b>Доступные пакеты:</b>\n"
    
    await message.answer(subscription_text, reply_markup=await kb.subscription_plans_keyboard())

@router.callback_query(F.data.startswith("subscribe_"))
async def process_subscription(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[1])
    plan = await rq.get_plan(plan_id)
    user = await rq.get_user(callback.from_user.id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    if plan:
        purchase_text = (
            f"📦 <b>Пакет подписки</b>\n\n"
            f"💎 Название: {plan.name}\n"
            f"⭐ Цена: {plan.price} Stars\n"
            f"📅 Длительность: {plan.duration_days} дней\n"
            f"📝 {plan.description}\n\n"
            f"💰 <b>Ваш баланс:</b> {user.stars_balance} Stars\n\n"
        )
        
        if user.stars_balance >= plan.price:
            purchase_text += "✅ Достаточно Stars для покупки!\nНажмите кнопку ниже для активации:"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🛒 Купить за {plan.price} ⭐", callback_data=f"confirm_subscribe_{plan_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_subscriptions")]
            ])
        else:
            purchase_text += f"❌ Недостаточно Stars. Нужно еще {plan.price - user.stars_balance} ⭐"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💫 Пополнить баланс", callback_data="buy_stars")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_subscriptions")]
            ])
        
        await callback.message.edit_text(purchase_text, reply_markup=keyboard)
    else:
        await callback.message.edit_text("❌ Пакет не найден")
    
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_subscribe_"))
async def confirm_subscription(callback: CallbackQuery):
    plan_id = int(callback.data.split("_")[2])
    result = await rq.purchase_subscription(callback.from_user.id, plan_id)
    
    if result['success']:
        # Создаем VLESS конфиг для пользователя
        duration_days = result.get('duration_days', 30)
        vless_result = vless_manager.create_vless_config(callback.from_user.id, duration_days)
        
        expire_date = datetime.fromtimestamp(vless_result["config"]["expires_at"])
        
        await callback.message.edit_text(
            f"🎉 {result['message']}\n\n"
            f"🔑 <b>Ваш VPN ключ создан!</b>\n"
            f"📅 Действует до: {expire_date.strftime('%d.%m.%Y')}\n"
            f"⭐ Списано: {result.get('stars_used', 0)} Stars\n"
            f"💫 Остаток на балансе: {result.get('remaining_balance', 0)} Stars\n\n"
            f"Используйте кнопку \"🔑 Мой VPN ключ\" для получения конфигурации.\n\n"
            f"Спасибо за покупку!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔑 Получить VPN ключ", callback_data="get_vless_key")],
                [InlineKeyboardButton(text="👤 В профиль", callback_data="my_profile")]
            ])
        )
    else:
        await callback.message.edit_text(f"❌ {result['message']}")
    
    await callback.answer()

# ======= ОСТАЛЬНЫЕ ОБРАБОТЧИКИ =======

@router.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)
    ref_code = None
    if len(args) > 1:
        ref_code = args[1].replace("/start", "").strip()

    try:
        member = await message.bot.get_chat_member(CHANNEL, message.from_user.id)
        if member.status in ("creator", "administrator", "member"):
            user = await rq.add_user_if_not_exists(
                tg_id=message.from_user.id,
                ref_code=uuid4().hex[:8],
                invited_by=ref_code if ref_code else None,
                expires=datetime.utcnow() + timedelta(hours=24)
            )

            await message.answer(
                f"🎉 Добро пожаловать в VPN бот!\n\n"
                f"💫 Ваш пробный период: 24 часа\n"
                f"💰 Баланс Stars: 0 ⭐\n\n"
                f"📢 Приглашайте друзей и получайте бонусы!\n"
                f"🔗 Ваша реферальная ссылка:\n"
                f"https://t.me/{(await message.bot.get_me()).username}?start={user.ref_code}",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
        else:
            await message.answer(
                f"📢 Чтобы пользоваться ботом, подпишитесь на наш канал:\n{CHANNEL}\n\n"
                f"После подписки нажмите кнопку проверки👇",
                reply_markup=kb.subscribe_keyboard(CHANNEL)
            )
    except Exception as e:
        await message.answer(f"⚠️ Произошла ошибка: {e}")

@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    profile_data = await rq.get_user_profile(message.from_user.id)
    if not profile_data:
        await message.answer("❌ Профиль не найден")
        return
        
    user = profile_data['user']
    referrals_count = profile_data['referrals_count']
    
    is_active, status_text = await rq.check_subscription_status(message.from_user.id)
    
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: {user.tg_id}\n"
        f"👤 Имя: {user.first_name or 'Не указано'} {user.last_name or ''}\n"
        f"📧 Username: @{user.username or 'Не указан'}\n"
        f"📅 Регистрация: {user.registration_date.strftime('%d.%m.%Y')}\n\n"
        f"⭐ <b>Баланс Stars:</b> {user.stars_balance}\n"
        f"💰 Всего заработано: {user.total_earned_stars} ⭐\n\n"
        f"📊 <b>Реферальная система:</b>\n"
        f"👥 Приглашено друзей: {referrals_count}\n"
        f"🔗 Ваша ссылка:\n"
        f"https://t.me/{(await message.bot.get_me()).username}?start={user.ref_code}\n\n"
        f"🛡️ <b>Статус подписки:</b>\n"
        f"{'✅ ' + status_text if is_active else '❌ ' + status_text}"
    )
    
    await message.answer(profile_text, reply_markup=kb.profile_keyboard())

async def show_vless_key_message(message: Message):
    """Показывает VLESS ключ пользователя"""
    user = await rq.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Проверяем активна ли подписка
    is_active, status_text = await rq.check_subscription_status(message.from_user.id)
    
    if not is_active:
        await message.answer(
            f"❌ У вас нет активной подписки!\n\n"
            f"{status_text}\n\n"
            f"Приобретите подписку в разделе \"📦 Подписка\"",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    # Получаем или создаем VLESS конфиг
    vless_config = vless_manager.get_user_config(message.from_user.id)
    
    if not vless_config:
        # Определяем длительность подписки
        duration_days = await _get_subscription_duration(message.from_user.id)
        if duration_days == 0:
            await message.answer("❌ Не удалось определить длительность подписки")
            return
        
        # Создаем новый конфиг
        result = vless_manager.create_vless_config(message.from_user.id, duration_days)
        vless_config = result["config"]
        vless_link = result["vless_link"]
    else:
        # Проверяем не истекла ли подписка
        if datetime.now().timestamp() > vless_config["expires_at"]:
            vless_manager.deactivate_user(message.from_user.id)
            await message.answer("❌ Срок действия вашего VPN ключа истек!")
            return
        
        vless_link = vless_manager._generate_vless_link(
            vless_config["uuid"], 
            vless_config["ws_path"], 
            vless_config["email"]
        )

    # Создаем QR код
    qr_img = qrcode.make(vless_link)
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    buf.seek(0)
    
    # Форматируем дату истечения
    expire_date = datetime.fromtimestamp(vless_config["expires_at"])
    days_left = (expire_date - datetime.now()).days
    
    # Отправляем сообщение с QR кодом и ссылкой
    message_text = (
        f"🔑 <b>Ваш VPN ключ</b>\n\n"
        f"🆔 Пользователь: {vless_config['email']}\n"
        f"📅 Действует до: {expire_date.strftime('%d.%m.%Y %H:%M')}\n"
        f"⏳ Осталось дней: {days_left}\n\n"
        f"<b>Ссылка для подключения:</b>\n"
        f"<code>{vless_link}</code>\n\n"
        f"📱 <b>Инструкция по использованию:</b>\n"
        f"1. Скачайте приложение V2RayNG (Android) или Shadowrocket (iOS)\n"
        f"2. Нажмите \"+\" для добавления конфигурации\n"
        f"3. Выберите \"Импорт из буфера обмена\"\n"
        f"4. Или отсканируйте QR код ниже\n\n"
        f"⚠️ <b>Не передавайте эту ссылку третьим лицам!</b>"
    )
    
    # Отправляем текст и QR код
    await message.answer_photo(photo=('qrcode.png', buf), caption=message_text)

@router.message(F.text == "🔑 Мой VPN ключ")
async def show_vless_key(message: Message):
    await show_vless_key_message(message)

async def show_vless_key_message(message: Message):
    """Показывает VLESS ключ пользователя"""
    user = await rq.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return

@router.message(F.text == "🔄 Обновить ключ")
async def refresh_vless_key(message: Message):
    """Обновляет VLESS ключ пользователя"""
    user = await rq.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Проверяем активна ли подписка
    is_active, status_text = await rq.check_subscription_status(message.from_user.id)
    
    if not is_active:
        await message.answer(
            f"❌ У вас нет активной подписки!\n\n"
            f"{status_text}\n\n"
            f"Приобретите подписку в разделе \"📦 Подписка\"",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    # Получаем или создаем VLESS конфиг
    vless_config = vless_manager.get_user_config(message.from_user.id)
    
    if not vless_config:
        # Определяем длительность подписки
        duration_days = await _get_subscription_duration(message.from_user.id)
        if duration_days == 0:
            await message.answer("❌ Не удалось определить длительность подписки")
            return
        
        # Создаем новый конфиг
        result = vless_manager.create_vless_config(message.from_user.id, duration_days)
        vless_config = result["config"]
        vless_link = result["vless_link"]
    else:
        # Проверяем не истекла ли подписка
        if datetime.now().timestamp() > vless_config["expires_at"]:
            vless_manager.deactivate_user(message.from_user.id)
            await message.answer("❌ Срок действия вашего VPN ключа истек!")
            return
        
        vless_link = vless_manager._generate_vless_link(
            vless_config["uuid"], 
            vless_config["ws_path"], 
            vless_config["email"]
        )

    # Создаем QR код
    qr_img = qrcode.make(vless_link)
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    buf.seek(0)
    
    # Форматируем дату истечения
    expire_date = datetime.fromtimestamp(vless_config["expires_at"])
    days_left = (expire_date - datetime.now()).days
    
    # Отправляем сообщение с QR кодом и ссылкой
    message_text = (
        f"🔑 <b>Ваш VPN ключ</b>\n\n"
        f"🆔 Пользователь: {vless_config['email']}\n"
        f"📅 Действует до: {expire_date.strftime('%d.%m.%Y %H:%M')}\n"
        f"⏳ Осталось дней: {days_left}\n\n"
        f"<b>Ссылка для подключения:</b>\n"
        f"<code>{vless_link}</code>\n\n"
        f"📱 <b>Инструкция по использованию:</b>\n"
        f"1. Скачайте приложение V2RayNG (Android) или Shadowrocket (iOS)\n"
        f"2. Нажмите \"+\" для добавления конфигурации\n"
        f"3. Выберите \"Импорт из буфера обмена\"\n"
        f"4. Или отсканируйте QR код ниже\n\n"
        f"⚠️ <b>Не передавайте эту ссылку третьим лицам!</b>"
    )
    
    # Создаем BufferedInputFile для отправки фото
    photo_file = BufferedInputFile(buf.getvalue(), filename="qrcode.png")
    
    # Отправляем фото с текстом
    await message.answer_photo(
        photo=photo_file, 
        caption=message_text,
        reply_markup=get_main_keyboard(message.from_user.id)
    )

@router.message(F.text == "⭐ Мой баланс")
async def show_balance(message: Message):
    user = await rq.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Пользователь не найден")
    payments = await rq.get_user_payments(message.from_user.id, 5)
    transactions = await rq.get_user_transactions(message.from_user.id, 5)
    
    balance_text = f"⭐ <b>Ваш баланс:</b> {user.stars_balance} Stars\n"
    balance_text += f"💰 <b>Всего заработано:</b> {user.total_earned_stars} Stars\n\n"
    
    if payments:
        balance_text += "💳 <b>Последние пополнения:</b>\n"
        for payment in payments[:3]:
            status_icon = "✅" if payment.status == 'completed' else "⏳"