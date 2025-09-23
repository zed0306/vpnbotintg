from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ContentType, ReplyKeyboardMarkup, KeyboardButton
import logging

logger = logging.getLogger(__name__)

# СОЗДАЕМ РОУТЕР
router = Router()

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Подписка"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="⭐ Баланс"), KeyboardButton(text="👥 Рефералы")],
        ],
        resize_keyboard=True
    )

class Register(StatesGroup):
    name = State()
    age = State()
    contact = State()

@router.message(F.text == 'Регистрация')
async def start_register(message: Message, state: FSMContext):
    await state.set_state(Register.name)
    await message.answer("👤 Введите ваше имя:")

@router.message(Register.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Register.age)
    await message.answer("🎂 Введите ваш возраст:")

@router.message(Register.age)
async def get_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Возраст должен быть числом. Попробуйте еще раз:")
        return
        
    await state.update_data(age=message.text)
    await state.set_state(Register.contact)
    await message.answer(
        "📞 Отправьте ваш номер телефона:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

@router.message(Register.contact, F.content_type == ContentType.CONTACT)
async def get_contact(message: Message, state: FSMContext):
    contact = message.contact.phone_number
    await state.update_data(contact=contact)
    data = await state.get_data()
    
    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"• Имя: {data.get('name')}\n"
        f"• Возраст: {data.get('age')}\n"
        f"• Номер: {data.get('contact')}",
        reply_markup=get_main_keyboard()
    )
    await state.clear()