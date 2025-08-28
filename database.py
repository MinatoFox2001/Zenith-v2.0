import asyncpg
from dataclasses import dataclass
from typing import Optional
import logging
from enum import Enum

class UserState(str, Enum):
    MAIN = "main"
    ADMIN = "admin"
    AWAITING_INPUT = "awaiting_input"

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "telegram_bot"
    user: str = "bot_user"
    password: str = "your_password"

class Database:
    _instance = None
    
    def __new__(cls, config: DatabaseConfig):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: DatabaseConfig):
        if self._initialized:
            return
            
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self.logger = logging.getLogger(__name__)
        self._initialized = True

    async def connect(self):
        """Установка соединения с базой данных"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=1,
                max_size=10
            )
            self.logger.info("✅ Connected to PostgreSQL database")
            
            # Создаем таблицы при первом подключении
            await self.create_tables()
            
        except Exception as e:
            self.logger.error(f"❌ Database connection error: {e}")
            raise

    async def create_tables(self):
        """Создание таблиц"""
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            username VARCHAR(255),
            state VARCHAR(50) DEFAULT 'main',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(create_users_table)
                self.logger.info("✅ Tables created successfully")
        except Exception as e:
            self.logger.error(f"❌ Error creating tables: {e}")
            raise

    async def add_user(self, user_id: int, first_name: str, last_name: str, username: str):
        """Добавление пользователя в базу данных"""
        query = """
        INSERT INTO users (user_id, first_name, last_name, username, state)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            username = EXCLUDED.username,
            updated_at = CURRENT_TIMESTAMP
        RETURNING state
        """
        
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(query, user_id, first_name, last_name, username, UserState.MAIN.value)
                self.logger.info(f"✅ User {user_id} added/updated in database")
                return UserState(result) if result else UserState.MAIN
        except Exception as e:
            self.logger.error(f"❌ Error adding user: {e}")
            return UserState.MAIN

    async def get_user(self, user_id: int):
        """Получение пользователя из базы данных"""
        query = "SELECT * FROM users WHERE user_id = $1"
        
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchrow(query, user_id)
                return result
        except Exception as e:
            self.logger.error(f"❌ Error getting user: {e}")
            return None

    async def get_user_state(self, user_id: int):
        """Получение состояния пользователя"""
        query = "SELECT state FROM users WHERE user_id = $1"
        
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(query, user_id)
                return UserState(result) if result else UserState.MAIN
        except Exception as e:
            self.logger.error(f"❌ Error getting user state: {e}")
            return UserState.MAIN

    async def set_user_state(self, user_id: int, state: UserState):
        """Установка состояния пользователя"""
        query = "UPDATE users SET state = $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $2"
        
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query, state.value, user_id)
                self.logger.info(f"✅ User {user_id} state changed to {state}")
        except Exception as e:
            self.logger.error(f"❌ Error setting user state: {e}")

    async def get_all_users(self):
        """Получение всех пользователей"""
        query = "SELECT * FROM users ORDER BY created_at DESC"
        
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetch(query)
                return result
        except Exception as e:
            self.logger.error(f"❌ Error getting users: {e}")
            return []

    async def get_users_count(self):
        """Получение количества пользователей"""
        query = "SELECT COUNT(*) FROM users"
        
        try:
            async with self.pool.acquire() as connection:
                result = await connection.fetchval(query)
                return result
        except Exception as e:
            self.logger.error(f"❌ Error getting users count: {e}")
            return 0

    async def close(self):
        """Закрытие соединения с базой данных"""
        if self.pool:
            await self.pool.close()
            self.logger.info("✅ Database connection closed")