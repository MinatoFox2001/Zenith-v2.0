from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import BotConfig
import logging

logger = logging.getLogger(__name__)

class AdminManager:
    def __init__(self, database):
        self.database = database
        self.admin_ids = BotConfig().admin_ids

    def is_admin(self, user: types.User) -> bool:
        result = user.id in self.admin_ids
        logger.info(f"Checking admin status for user {user.id} ({user.username}): {result}")
        return result

    def get_admin_keyboard(self):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👥 Все пользователи"), KeyboardButton(text="📊 Статистика админа")],
                [KeyboardButton(text="🔙 Основное меню")]
            ],
            resize_keyboard=True
        )

    async def show_all_users(self, message: types.Message, message_manager, reply_markup=None):
        try:
            # Удаляем предыдущее сообщение пользователя
            await message_manager.delete_previous_message(message.from_user.id)
            
            users = await self.database.get_all_users()
            
            if not users:
                await message_manager.send_or_edit_message(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    text="📭 В базе данных нет пользователей",
                    reply_markup=reply_markup
                )
                return
            
            users_text = "👥 Все пользователи:\n\n"
            for i, user in enumerate(users, 1):
                users_text += f"{i}. {user['first_name']}"
                if user['last_name']:
                    users_text += f" {user['last_name']}"
                if user['username']:
                    users_text += f" (@{user['username']})"
                users_text += f" - ID: {user['user_id']}\n"
                users_text += f"   Состояние: {user['state']}\n"
                users_text += f"   Зарегистрирован: {user['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
            
            # Разбиваем сообщение если слишком длинное
            if len(users_text) > 4000:
                parts = [users_text[i:i+4000] for i in range(0, len(users_text), 4000)]
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        await message_manager.send_or_edit_message(
                            chat_id=message.chat.id,
                            user_id=message.from_user.id,
                            text=part,
                            reply_markup=reply_markup
                        )
                    else:
                        await message_manager.send_or_edit_message(
                            chat_id=message.chat.id,
                            user_id=message.from_user.id,
                            text=part
                        )
            else:
                await message_manager.send_or_edit_message(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    text=users_text,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error showing users: {e}")
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text="❌ Ошибка при получении пользователей",
                reply_markup=reply_markup
            )

    async def show_admin_stats(self, message: types.Message, message_manager, reply_markup=None):
        try:
            # Удаляем предыдущее сообщение пользователя
            await message_manager.delete_previous_message(message.from_user.id)
            
            users = await self.database.get_all_users()
            users_count = await self.database.get_users_count()
            
            stats_text = f"""
            📊 Статистика админа:
            
            👥 Всего пользователей: {users_count}
            """
            
            if users:
                stats_text += f"📅 Последняя регистрация: {users[0]['created_at'].strftime('%d.%m.%Y %H:%M')}"
                
                # Статистика по состояниям
                state_stats = {}
                for user in users:
                    state = user['state']
                    state_stats[state] = state_stats.get(state, 0) + 1
                
                stats_text += "\n\n📊 Распределение по состояниям:"
                
                for state, count in state_stats.items():
                    stats_text += f"\n• {state}: {count} пользователей"
                
                stats_text += "\n\n📈 Последние 5 пользователей:"
                
                for i, user in enumerate(users[:5], 1):
                    stats_text += f"\n{i}. {user['first_name']} (@{user['username'] or 'нет username'}) - {user['state']}"
            
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text=stats_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text="❌ Ошибка при получении статистики",
                reply_markup=reply_markup
            )

    async def back_to_main_menu(self, message: types.Message, message_manager):
        from database import UserState
        await self.database.set_user_state(message.from_user.id, UserState.MAIN)
        
        # Очищаем историю сообщений пользователя
        message_manager.clear_user_messages(message.from_user.id)