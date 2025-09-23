from sqlalchemy import select, func, update, insert, desc
from app.database.models import async_session, User, Broadcast, SubscriptionPlan, UserSubscription, StarsTransaction, Payment
from datetime import datetime, timedelta

async def init_subscription_plans():
    """Инициализация пакетов подписки"""
    async with async_session() as session:
        plans_data = [
            {"name": "1 месяц", "duration_days": 30, "price": 100, "description": "VPN доступ на 1 месяц"},
            {"name": "3 месяца", "duration_days": 90, "price": 250, "description": "VPN доступ на 3 месяца (экономия 17%)"},
            {"name": "6 месяцев", "duration_days": 180, "price": 350, "description": "VPN доступ на 6 месяцев (экономия 42%)"},
            {"name": "1 год", "duration_days": 365, "price": 500, "description": "VPN доступ на 1 год (экономия 58%)"},
        ]
        
        for plan_data in plans_data:
            existing = await session.scalar(
                select(SubscriptionPlan).where(SubscriptionPlan.name == plan_data["name"])
            )
            if not existing:
                plan = SubscriptionPlan(**plan_data)
                session.add(plan)
        
        await session.commit()
        print("✅ Пакеты подписки инициализированы")

async def set_user(tg_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Создаёт или обновляет пользователя"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            if last_name and user.last_name != last_name:
                user.last_name = last_name
            user.last_activity = datetime.utcnow()
            await session.commit()
            return user
        else:
            from uuid import uuid4
            new_user = User(
                tg_id=tg_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                ref_code=uuid4().hex[:8],
                expires=datetime.utcnow() + timedelta(hours=24),
                registration_date=datetime.utcnow(),
                last_activity=datetime.utcnow()
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user

async def get_user(tg_id: int):
    async with async_session() as session:
        return await session.scalar(select(User).where(User.tg_id == tg_id))

async def get_user_profile(tg_id: int):
    """Получает полную информацию о пользователе для профиля"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            referrals_count = await session.scalar(
                select(func.count(User.id)).where(User.invited_by == user.ref_code)
            )
            
            active_subscription = await session.scalar(
                select(UserSubscription).where(
                    UserSubscription.user_id == user.id,
                    UserSubscription.is_active == True,
                    UserSubscription.end_date > datetime.utcnow()
                )
            )
            
            return {
                'user': user,
                'referrals_count': referrals_count,
                'active_subscription': active_subscription
            }
        return None
    
async def _get_subscription_duration(telegram_id: int) -> int:
    """Определяет длительность подписки пользователя в днях"""
    async with async_session() as session:
        from app.database.models import UserSubscription, SubscriptionPlan
        
        subscription = await session.scalar(
            select(UserSubscription).where(
                UserSubscription.user_id == telegram_id,
                UserSubscription.is_active == True
            )
        )
        
        if subscription and subscription.plan:
            return subscription.plan.duration_days
        
        # Если подписка не найдена, проверяем пробный период
        user = await session.scalar(select(User).where(User.tg_id == telegram_id))
        if user and user.expires and user.expires > datetime.utcnow():
            days_left = (user.expires - datetime.utcnow()).days
            return max(1, days_left)  # Минимум 1 день
        
        return 0
    
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
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    
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
    
    # Для отправки изображения нужно использовать другой метод
    # Временно отправляем только текст с ссылкой
    await message.answer(message_text)
    
    
    # Деактивируем старый ключ
    vless_manager.deactivate_user(message.from_user.id)
    
    # Создаем новый ключ
    duration_days = await _get_subscription_duration(message.from_user.id)
    result = vless_manager.create_vless_config(message.from_user.id, duration_days)
    
    expire_date = datetime.fromtimestamp(result["config"]["expires_at"])
    
    await message.answer(
        f"✅ <b>VPN ключ успешно обновлен!</b>\n\n"
        f"🔑 Новый ключ создан\n"
        f"📅 Действует до: {expire_date.strftime('%d.%m.%Y')}\n\n"
        f"Используйте кнопку \"🔑 Мой VPN ключ\" для получения новой ссылки.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


async def add_user_if_not_exists(tg_id: int, ref_code: str, invited_by: str = None, expires: datetime = None):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            from uuid import uuid4
            new_user = User(
                tg_id=tg_id,
                ref_code=ref_code or uuid4().hex[:8],
                invited_by=invited_by,
                expires=expires or (datetime.utcnow() + timedelta(hours=24)),
                registration_date=datetime.utcnow(),
                last_activity=datetime.utcnow()
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            
            if invited_by:
                await add_bonus_days_to_ref(invited_by, 7)
                await add_stars_to_user_by_ref_code(invited_by, 10)
                
            return new_user
        return user

async def add_stars_to_user(tg_id: int, amount: int, transaction_type: str, description: str = ""):
    """Добавляет stars пользователю и создает запись в транзакциях"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            user.stars_balance += amount
            if amount > 0:
                user.total_earned_stars += amount
            
            transaction = StarsTransaction(
                user_id=user.id,
                amount=amount,
                transaction_type=transaction_type,
                description=description
            )
            session.add(transaction)
            await session.commit()
            return True
        return False

async def add_stars_to_user_by_ref_code(ref_code: str, amount: int):
    """Добавляет stars пользователю по реферальному коду"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.ref_code == ref_code))
        if user:
            return await add_stars_to_user(user.tg_id, amount, 'referral', 'Бонус за приглашение')
        return False

async def get_user_transactions(tg_id: int, limit: int = 10):
    """Получает историю транзакций пользователя"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            transactions = await session.scalars(
                select(StarsTransaction)
                .where(StarsTransaction.user_id == user.id)
                .order_by(desc(StarsTransaction.created_at))
                .limit(limit)
            )
            return transactions.all()
        return []

async def update_referral_bonus(user_id: int) -> int:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if not user:
            return 0
            
        referrals_count = await session.scalar(
            select(func.count(User.id)).where(User.invited_by == user.ref_code)
        )
        
        total_bonus = referrals_count * 7
        return total_bonus

async def add_bonus_days_to_ref(ref_code: str, days: int):
    async with async_session() as session:
        ref_user = await session.scalar(select(User).where(User.ref_code == ref_code))
        if not ref_user:
            return False
            
        if not ref_user.expires or ref_user.expires < datetime.utcnow():
            ref_user.expires = datetime.utcnow() + timedelta(days=days)
        else:
            ref_user.expires += timedelta(days=days)
            
        await session.commit()
        return True

async def count_users():
    async with async_session() as s:
        return await s.scalar(select(func.count(User.id)))

async def get_all_users():
    async with async_session() as s:
        return (await s.execute(select(User))).scalars().all()

async def save_broadcast(text, total):
    async with async_session() as s:
        b = Broadcast(text=text, total=total)
        s.add(b)
        await s.commit()
        await s.refresh(b)
        return b

async def count_broadcasts():
    async with async_session() as s:
        return await s.scalar(select(func.count(Broadcast.id)))

async def update_broadcast_sent(b_id, sent):
    async with async_session() as s:
        await s.execute(
            update(Broadcast).where(Broadcast.id == b_id).values(sent=sent)
        )
        await s.commit()

async def get_subscription_plans():
    async with async_session() as session:
        return await session.scalars(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True))

async def get_plan(plan_id: int):
    async with async_session() as session:
        return await session.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))

async def purchase_subscription(tg_id: int, plan_id: int) -> dict:
    """Покупка подписки за stars"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        plan = await session.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        
        if not user or not plan:
            return {'success': False, 'message': 'Пользователь или план не найден'}
            
        if user.stars_balance < plan.price:
            return {'success': False, 'message': f'Недостаточно Stars. Нужно: {plan.price}, у вас: {user.stars_balance}'}
        
        user.stars_balance -= plan.price
        
        await session.execute(
            update(UserSubscription)
            .where(UserSubscription.user_id == user.id)
            .values(is_active=False)
        )
        
        end_date = datetime.utcnow() + timedelta(days=plan.duration_days)
        new_sub = UserSubscription(
            user_id=user.id,
            plan_id=plan_id,
            start_date=datetime.utcnow(),
            end_date=end_date,
            is_active=True,
            stars_paid=plan.price
        )
        session.add(new_sub)
        
        user.expires = end_date
        
        transaction = StarsTransaction(
            user_id=user.id,
            amount=-plan.price,
            transaction_type='purchase',
            description=f'Покупка подписки: {plan.name}'
        )
        session.add(transaction)
        
        await session.commit()
        
        return {
            'success': True, 
            'message': f'Подписка "{plan.name}" активирована до {end_date.strftime("%d.%m.%Y")}',
            'end_date': end_date,
            'duration_days': plan.duration_days,
            'stars_used': plan.price,
            'remaining_balance': user.stars_balance
        }

async def check_subscription_status(tg_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False, "Пользователь не найден"
            
        if user.expires and user.expires > datetime.utcnow():
            days_left = (user.expires - datetime.utcnow()).days
            status_text = f"Подписка активна до {user.expires.strftime('%d.%m.%Y')} ({days_left} дней осталось)"
            return True, status_text
        else:
            return False, "Подписка истекла"

async def create_payment(user_id: int, amount: int, invoice_payload: str = "") -> Payment:
    """Создает запись о платеже"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        if not user:
            return None
            
        payment = Payment(
            user_id=user_id,
            amount=amount,
            invoice_payload=invoice_payload,
            status='pending'
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment

async def complete_payment(payment_id: int, provider_payment_charge_id: str, telegram_payment_charge_id: str) -> bool:
    """Завершает платеж и начисляет stars"""
    async with async_session() as session:
        payment = await session.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment:
            return False
            
        payment.status = 'completed'
        payment.provider_payment_charge_id = provider_payment_charge_id
        payment.telegram_payment_charge_id = telegram_payment_charge_id
        payment.completed_at = datetime.utcnow()
        
        user = await session.scalar(select(User).where(User.id == payment.user_id))
        user.stars_balance += payment.amount
        user.total_earned_stars += payment.amount
        
        transaction = StarsTransaction(
            user_id=user.id,
            amount=payment.amount,
            transaction_type='deposit',
            description='Пополнение баланса через Telegram Stars'
        )
        session.add(transaction)
        
        await session.commit()
        return True

async def get_user_payments(tg_id: int, limit: int = 10):
    """Получает историю платежей пользователя"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            payments = await session.scalars(
                select(Payment)
                .where(Payment.user_id == user.id)
                .order_by(desc(Payment.created_at))
                .limit(limit)
            )
            return payments.all()
        return []