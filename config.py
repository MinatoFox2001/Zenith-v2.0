from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class BotConfig:
    token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: list = field(default_factory=list)
    
    def __post_init__(self):
        # Получаем ID админов из переменных окружения
        admin_ids_raw = os.getenv("ADMIN_IDS", "")
        if admin_ids_raw:
            self.admin_ids = [int(admin_id.strip()) for admin_id in admin_ids_raw.split(",") if admin_id.strip().isdigit()]
        print(f"DEBUG: Admin IDs: {self.admin_ids}")

@dataclass
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", 5432))
    database: str = os.getenv("DB_NAME", "telegram_bot")
    user: str = os.getenv("DB_USER", "bot_user")
    password: str = os.getenv("DB_PASSWORD", "your_password")