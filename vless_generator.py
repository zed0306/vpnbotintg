import json
import uuid
from datetime import datetime
import sqlite3
import hashlib
import urllib.parse
from typing import Dict, Optional

class AdvancedVlessConfigManager:
    def __init__(self, domain: str):
        self.domain = domain
        self.users_db = "/home/vpnbot/vpn-bot/vless_users.db"
        self.xray_config_path = "/usr/local/etc/xray/config.json"
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
                is_active BOOLEAN DEFAULT TRUE,
                traffic_used INTEGER DEFAULT 0,
                last_connected TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def generate_stealth_config(self, telegram_id: int, duration_days: int) -> Dict:
        """Создает конфигурацию с маскировкой под популярные сервисы"""
        user_uuid = str(uuid.uuid4())
        
        # Генерируем уникальные пути для маскировки
        ws_paths = {
            'netflix': f"/video/{hashlib.md5(f'{telegram_id}netflix'.encode()).hexdigest()[:12]}",
            'youtube': f"/stream/{hashlib.md5(f'{telegram_id}youtube'.encode()).hexdigest()[:12]}",
            'whatsapp': f"/api/{hashlib.md5(f'{telegram_id}whatsapp'.encode()).hexdigest()[:12]}",
            'primary': f"/vless/{hashlib.md5(f'{telegram_id}primary'.encode()).hexdigest()[:10]}"
        }
        
        user_email = f"user{telegram_id}@{self.domain}"
        expire_timestamp = datetime.now().timestamp() + (duration_days * 24 * 60 * 60)
        
        # Сохраняем в базу данных
        conn = sqlite3.connect(self.users_db)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM vless_users WHERE telegram_id = ?", (telegram_id,))
        
        cursor.execute('''
            INSERT INTO vless_users 
            (telegram_id, uuid, ws_path, email, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (telegram_id, user_uuid, json.dumps(ws_paths), user_email, 
              datetime.now().isoformat(), expire_timestamp, True))
        
        conn.commit()
        conn.close()
        
        # Генерируем ссылки для разных сервисов
        vless_links = {}
        for service, path in ws_paths.items():
            vless_links[service] = self._generate_stealth_link(user_uuid, path, user_email, service)
        
        return {
            "config": {
                "telegram_id": telegram_id,
                "uuid": user_uuid,
                "ws_paths": ws_paths,
                "email": user_email,
                "created_at": datetime.now().isoformat(),
                "expires_at": expire_timestamp,
                "is_active": True
            },
            "vless_links": vless_links,
            "primary_link": vless_links['primary']
        }
    
    def _generate_stealth_link(self, user_uuid: str, ws_path: str, user_email: str, service: str) -> str:
        """Генерирует VLESS ссылку с маскировкой под конкретный сервис"""
        encoded_path = urllib.parse.quote(ws_path, safe='')
        
        # Добавляем заголовки для маскировки
        headers = f"Host: {self.domain}"
        if service == 'netflix':
            headers += "&X-Forwarded-For: 1.1.1.1&User-Agent: Mozilla/5.0"
        elif service == 'youtube':
            headers += "&Referer: https://www.youtube.com/&User-Agent: Mozilla/5.0"
        
        vless_link = (
            f"vless://{user_uuid}@{self.domain}:443?"
            f"encryption=none&"
            f"flow=xtls-rprx-vision&"
            f"security=tls&"
            f"type=ws&"
            f"path={encoded_path}&"
            f"host={self.domain}&"
            f"sni={self.domain}&"
            f"fp=chrome&"
            f"alpn=h2,http/1.1&"
            f"allowInsecure=0#"
            f"{urllib.parse.quote(user_email + ' - ' + service)}"
        )
        return vless_link
    
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
                "ws_paths": json.loads(row[3]),
                "email": row[4],
                "created_at": row[5],
                "expires_at": row[6],
                "is_active": bool(row[7]),
                "traffic_used": row[8],
                "last_connected": row[9]
            }
        return None

# Инициализация менеджера
vless_manager = AdvancedVlessConfigManager(domain="waterdropvpn.ru")