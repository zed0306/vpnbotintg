import json
import subprocess
import uuid
from datetime import datetime
import sqlite3
import os
from typing import Dict, Optional
import urllib.parse
import hashlib

class VlessConfigManager:
    def __init__(self, domain: str, xray_config_path: str = "/usr/local/etc/xray/config.json"):
        self.domain = domain
        self.xray_config_path = xray_config_path
        self.base_ws_path = "/vless/"
        
    def generate_user_uuid(self) -> str:
        """Генерирует UUID для пользователя"""
        return str(uuid.uuid4())
    
    def generate_ws_path(self, telegram_id: int) -> str:
        """Генерирует уникальный WebSocket путь"""
        return self.base_ws_path + hashlib.md5(f"{telegram_id}{datetime.now().timestamp()}".encode()).hexdigest()[:10]
    
    def create_vless_config(self, telegram_id: int, duration_days: int) -> Dict:
        """Создает VLESS конфигурацию для пользователя"""
        user_uuid = self.generate_user_uuid()
        ws_path = self.generate_ws_path(telegram_id)
        user_email = f"user{telegram_id}@{self.domain}"
        
        # Рассчитываем дату истечения
        expire_date = datetime.now().timestamp() + (duration_days * 24 * 60 * 60)
        
        # Создаем конфиг пользователя
        user_config = {
            "telegram_id": telegram_id,
            "uuid": user_uuid,
            "ws_path": ws_path,
            "email": user_email,
            "created_at": datetime.now().isoformat(),
            "expires_at": expire_date,
            "is_active": True
        }
        
        # Генерируем VLESS ссылку
        vless_link = self._generate_vless_link(user_uuid, ws_path, user_email)
        
        return {
            "config": user_config,
            "vless_link": vless_link,
            "qr_code_data": vless_link  # Для генерации QR кода
        }
    
    def _generate_vless_link(self, user_uuid: str, ws_path: str, user_email: str) -> str:
        """Генерирует VLESS ссылку"""
        encoded_path = urllib.parse.quote(ws_path, safe='')
        
        vless_link = (
            f"vless://{user_uuid}@{self.domain}:443?"
            f"encryption=none&"
            f"flow=&"
            f"security=tls&"
            f"type=ws&"
            f"path={encoded_path}&"
            f"host={self.domain}&"
            f"sni={self.domain}#"
            f"{urllib.parse.quote(user_email)}"
        )
        return vless_link
    
    def add_user_to_xray(self, user_config: Dict) -> bool:
        """Добавляет пользователя в конфиг Xray (упрощенная версия)"""
        try:
            # Для продакшена нужно реализовать добавление в Xray config
            # Сейчас возвращаем True для демонстрации
            return True
        except Exception as e:
            print(f"Error adding user to Xray: {e}")
            return False
    
    def deactivate_user(self, telegram_id: int) -> bool:
        """Деактивирует пользователя в Xray"""
        try:
            # Реализация деактивации пользователя
            return True
        except Exception as e:
            print(f"Error deactivating user: {e}")
            return False

# Упрощенная версия для тестирования (без реального Xray)
class MockVlessConfigManager(VlessConfigManager):
    def __init__(self, domain: str):
        self.domain = domain
        self.users_db = "vless_users.db"
        self._init_database()
    
    def _init_database(self):
        """Инициализирует базу данных для хранения пользователей"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vless_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                uuid TEXT UNIQUE,
                ws_path TEXT,
                email TEXT,
                created_at TEXT,
                expires_at REAL,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        conn.commit()
        conn.close()
    
    def create_vless_config(self, telegram_id: int, duration_days: int) -> Dict:
        """Создает VLESS конфигурацию для пользователя"""
        user_uuid = self.generate_user_uuid()
        ws_path = self.generate_ws_path(telegram_id)
        user_email = f"user{telegram_id}@{self.domain}"
        expire_timestamp = datetime.now().timestamp() + (duration_days * 24 * 60 * 60)
        
        # Сохраняем в базу данных
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        # Удаляем старую запись если существует
        cursor.execute("DELETE FROM vless_users WHERE telegram_id = ?", (telegram_id,))
        
        # Добавляем новую запись
        cursor.execute('''
            INSERT INTO vless_users 
            (telegram_id, uuid, ws_path, email, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (telegram_id, user_uuid, ws_path, user_email, 
                datetime.now().isoformat(), expire_timestamp, True))
        
        conn.commit()
        conn.close()
        
        # Генерируем ссылку
        vless_link = self._generate_vless_link(user_uuid, ws_path, user_email)
        
        return {
            "config": {
                "telegram_id": telegram_id,
                "uuid": user_uuid,
                "ws_path": ws_path,
                "email": user_email,
                "created_at": datetime.now().isoformat(),
                "expires_at": expire_timestamp,
                "is_active": True
            },
            "vless_link": vless_link,
            "qr_code_data": vless_link
        }
    
    def get_user_config(self, telegram_id: int) -> Optional[Dict]:
        """Получает конфигурацию пользователя"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM vless_users WHERE telegram_id = ? AND is_active = 1
        ''', (telegram_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "telegram_id": row[1],
                "uuid": row[2],
                "ws_path": row[3],
                "email": row[4],
                "created_at": row[5],
                "expires_at": row[6],
                "is_active": bool(row[7])
            }
        return None
    
    def deactivate_user(self, telegram_id: int) -> bool:
        """Деактивирует пользователя"""
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE vless_users SET is_active = 0 WHERE telegram_id = ?
        ''', (telegram_id,))
        
        conn.commit()
        conn.close()
        return True

# Инициализация менеджера
# Для тестирования используем mock, для продакшена замените на VlessConfigManager
vless_manager = MockVlessConfigManager(domain="waterdropvpn.ru")  # Замените на ваш домен