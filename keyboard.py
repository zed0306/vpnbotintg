from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard(user_id: int, admin_id: int = 1411430230) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📦 Подписка")],
        [KeyboardButton(text="🔑 Мой VPN ключ"), KeyboardButton(text="⭐ Мой баланс")],
        [KeyboardButton(text="👥 Мои реффералы"), KeyboardButton(text="💫 Пополнить баланс")]
    ]
    if user_id == admin_id:
        keyboard.append([KeyboardButton(text="👨‍💻 Админка")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def subscribe_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить подписку ✅", callback_data="check_subscribe")],
        [InlineKeyboardButton(text="Перейти к каналу 🔗", url=f"https://t.me/{channel_username.strip('@')}")]
    ])
    return kb

def vpn_management_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Получить ключ", callback_data="get_vless_key")],
        [InlineKeyboardButton(text="🔄 Обновить ключ", callback_data="refresh_vless_key")],
        [InlineKeyboardButton(text="📊 Статистика использования", callback_data="vpn_stats")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    return kb

async def subscription_plans_keyboard():
    from app.database import requests as rq
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    plans = await rq.get_subscription_plans()
    
    for plan in plans:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{plan.name} - {plan.price} ⭐", 
                callback_data=f"subscribe_{plan.id}"
            )
        ])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="💫 Пополнить баланс", callback_data="buy_stars"),
        InlineKeyboardButton(text="📊 Мой профиль", callback_data="my_profile")
    ])
    return kb

def buy_stars_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100 ⭐", callback_data="stars_100"),
            InlineKeyboardButton(text="500 ⭐", callback_data="stars_500")
        ],
        [
            InlineKeyboardButton(text="1000 ⭐", callback_data="stars_1000"),
            InlineKeyboardButton(text="5000 ⭐", callback_data="stars_5000")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_subscriptions")]
    ])
    return kb

def profile_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Мой VPN ключ", callback_data="get_vless_key")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats")],
        [InlineKeyboardButton(text="💫 История платежей", callback_data="payment_history")],
        [InlineKeyboardButton(text="📢 Поделиться ссылкой", callback_data="share_ref_link")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])
    return kb

def back_to_profile_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в профиль", callback_data="my_profile")]
    ])
    return kb

def admin_main():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Статистика 👥", callback_data="admin_stats"),
            InlineKeyboardButton(text="Рассылка 📨", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="Пользователи 📊", callback_data="admin_users"),
            InlineKeyboardButton(text="Транзакции 💫", callback_data="admin_transactions")
        ]
    ])
    return kb

# Добавляем недостающие клавиатуры
def back_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def main_menu_keyboard(user_id: int):
    return get_main_keyboard(user_id)

contact_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)