from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, BigInteger, Text, Table
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3" 

engine = create_async_engine(DATABASE_URL, echo=True, future=True)

async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Вспомогательная таблица для рассылок
broadcast_users = Table(
    "broadcast_users",
    Base.metadata,
    Column("broadcast_id", Integer, ForeignKey("broadcasts.id")),
    Column("user_id", Integer, ForeignKey("users.id")),
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    ref_code = Column(String, unique=True, nullable=False)
    invited_by = Column(String, nullable=True)
    expires = Column(DateTime, default=datetime.utcnow)
    bonus_days = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    stars_balance = Column(Integer, default=0)
    total_earned_stars = Column(Integer, default=0)
    registration_date = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)

    payments = relationship("Payment", back_populates="user")
    subscriptions = relationship("UserSubscription", back_populates="user")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, nullable=False)
    status = Column(String, default='pending')
    provider_payment_charge_id = Column(String)
    telegram_payment_charge_id = Column(String)
    invoice_payload = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="payments")

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    duration_days = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(String)
    is_active = Column(Boolean, default=True)
    
    subscriptions = relationship("UserSubscription", back_populates="plan")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"))
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    stars_paid = Column(Integer)
    
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")

class StarsTransaction(Base):
    __tablename__ = "stars_transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    total = Column(Integer, default=0)
    sent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship(
        "User",
        secondary=broadcast_users,
        backref="broadcasts"
    )