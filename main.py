import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import BotConfig, DatabaseConfig
from database import Database, UserState
from middleware import UserStateMiddleware
from admin_manager import AdminManager
import logging

logging.basicConfig(level=logging.INFO)

class MessageManager:
    """Универсальный менеджер для работы с сообщениями"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.user_messages = {}  # Хранит последние сообщения по user_id
    
    async def send_or_edit_message(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup = None,
        parse_mode: str = None
    ) -> types.Message:
        """
        Универсальный метод для отправки или редактирования сообщения
        """
        if user_id in self.user_messages and self.user_messages[user_id].get('message_id'):
            try:
                # Пытаемся отредактировать существующее сообщение
                message = await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=self.user_messages[user_id]['message_id'],
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                self.user_messages[user_id] = {
                    'message_id': message.message_id,
                    'chat_id': chat_id
                }
                return message
            except Exception as e:
                # Если редактирование не удалось (например, сообщение было удалено),
                # отправляем новое сообщение и удаляем старое
                logging.warning(f"Failed to edit message: {e}. Sending new message.")
                await self.delete_previous_message(user_id)
        
        # Отправляем новое сообщение
        message = await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        
        self.user_messages[user_id] = {
            'message_id': message.message_id,
            'chat_id': chat_id
        }
        return message
    
    async def delete_previous_message(self, user_id: int):
        """Удаляет предыдущее сообщение пользователя"""
        if user_id in self.user_messages:
            try:
                await self.bot.delete_message(
                    chat_id=self.user_messages[user_id]['chat_id'],
                    message_id=self.user_messages[user_id]['message_id']
                )
            except Exception as e:
                logging.warning(f"Failed to delete message: {e}")
            finally:
                # Удаляем запись о сообщении
                self.user_messages.pop(user_id, None)
    
    def clear_user_messages(self, user_id: int):
        """Очищает историю сообщений пользователя"""
        self.user_messages.pop(user_id, None)

async def main():
    # Инициализация конфигурации
    bot_config = BotConfig()
    db_config = DatabaseConfig()
    
    # Инициализация базы данных
    database = Database(db_config)
    await database.connect()
    
    # Инициализация менеджера администраторов
    admin_manager = AdminManager(database)
    
    # Инициализация бота и диспетчера
    bot = Bot(token=bot_config.token)
    dp = Dispatcher()
    
    # Инициализация менеджера сообщений
    message_manager = MessageManager(bot)
    
    # Добавляем middleware для обработки состояний
    dp.message.middleware(UserStateMiddleware(database))
    dp.callback_query.middleware(UserStateMiddleware(database))
    
    # Создаем инлайн клавиатуры
    def get_main_inline_keyboard(is_admin: bool = False):
        keyboard = [
            [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="personal_cabinet")],
            [InlineKeyboardButton(text="ℹ️ О проекте", callback_data="about_project")]
        ]

        # Добавляем кнопку админа только если пользователь является администратором
        if is_admin:
            keyboard.insert(0, [InlineKeyboardButton(text="🛠️ Админ панель", callback_data="admin_panel")])

        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    def get_personal_cabinet_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Статистика", callback_data="user_stats")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
            ]
        )

    def get_back_to_main_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
            ]
        )

    def get_back_to_cabinet_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_cabinet")]
            ]
        )

    def get_admin_main_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_all_users")],
                [InlineKeyboardButton(text="📊 Статистика админа", callback_data="admin_stats")],
                [InlineKeyboardButton(text="🔙 Основное меню", callback_data="admin_back_to_main")]
            ]
        )

    def get_admin_back_keyboard():
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back_to_main_menu")]
            ]
        )

    # Обработчик команды /start
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message, user_state: UserState):
        # Удаляем сообщение пользователя с командой /start
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Failed to delete user message: {e}")
        
        # Сохраняем пользователя в базу данных и получаем состояние
        current_state = await database.add_user(
            user_id=message.from_user.id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name or "",
            username=message.from_user.username or ""
        )
        
        is_admin_user = admin_manager.is_admin(message.from_user)
        welcome_message = await get_welcome_message(message.from_user, is_admin_user)
        
        # Используем универсальный метод для отправки/редактирования сообщения
        await message_manager.send_or_edit_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            text=welcome_message,
            reply_markup=get_main_inline_keyboard(is_admin_user)
        )

    async def get_welcome_message(user: types.User, is_admin_user: bool = False) -> str:
        # Получаем количество пользователей
        users_count = await database.get_users_count()
            
        # Формируем username
        user_name = user.first_name or "друг"
            
        welcome_text = f"""
        🌟 Здравствуйте, {user_name}!\nЯ Zenith - ваш надежный помощник в решении различных задач.

        🚀 Чем могу помочь:
        • Ответить на ваши вопросы
        • Предоставить полезную информацию  
        • Помочь с различными вычислениями
        • Показать статистику и аналитику

        📊 Всего пользователей доверяют мне: {users_count}
                
        💡 Используйте кнопки ниже для взаимодействия!
            """
            
        if is_admin_user:
            welcome_text += "\n\n⚡ Вы являетесь администратором! Доступны дополнительные команды через /admin"
            
        return welcome_text

    # Команда /admin
    @dp.message(Command("admin"))
    async def cmd_admin(message: types.Message, user_state: UserState):
        # Удаляем сообщение пользователя с командой /admin
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Failed to delete user message: {e}")
        
        if not admin_manager.is_admin(message.from_user):
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text="⛔ У вас нет прав доступа к админ панели"
            )
            return
        
        # Устанавливаем состояние админа
        await database.set_user_state(message.from_user.id, UserState.ADMIN)
        
        admin_text = """
        🛠️ Админ панель
        
        Доступные функции:
        • Просмотр всех пользователей
        • Статистика бота
        
        Используйте кнопки ниже для управления!
        """
        await message_manager.send_or_edit_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            text=admin_text,
            reply_markup=get_admin_main_keyboard()
        )

    # Команда /users
    @dp.message(Command("users"))
    async def cmd_users(message: types.Message, user_state: UserState):
        # Удаляем сообщение пользователя с командой /users
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Failed to delete user message: {e}")
        
        if not admin_manager.is_admin(message.from_user):
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text="⛔ У вас нет прав доступа"
            )
            return
        
        await admin_manager.show_all_users(message, message_manager, get_admin_back_keyboard())

    # Команда /stats
    @dp.message(Command("stats"))
    async def cmd_stats(message: types.Message, user_state: UserState):
        # Удаляем сообщение пользователя с командой /stats
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Failed to delete user message: {e}")
        
        if not admin_manager.is_admin(message.from_user):
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text="⛔ У вас нет прав доступа"
            )
            return
        
        await admin_manager.show_admin_stats(message, message_manager, get_admin_back_keyboard())

    # Обработчик команды /help
    @dp.message(Command("help"))
    async def cmd_help(message: types.Message, user_state: UserState):
        # Удаляем сообщение пользователя с командой /help
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Failed to delete user message: {e}")
        
        help_text = """
                    🤖 Zenith - универсальный помощник

                    📋 Основные возможности:
                    • Консультации и ответы на вопросы
                    • Математические вычисления
                    • Статистика и аналитика
                    • Персонализированные уведомления

                    ⌨️ Основные команды:
                    /start - начать работу
                    /help - помощь и возможности
                    /info - ваша статистика
                    /ask [вопрос] - задать вопрос

                    🎛️ Или используйте инлайн кнопки!
                        """
        
        # Если пользователь админ, добавляем админские команды
        if admin_manager.is_admin(message.from_user):
            help_text += "\n\n🛠️ Админ команды:\n/admin - панель управления\n/users - список пользователей\n/stats - детальная статистика"
        
        await message_manager.send_or_edit_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            text=help_text
        )

    # Обработчик команды /info
    @dp.message(Command("info"))
    async def cmd_info(message: types.Message, user_state: UserState):
        # Удаляем сообщение пользователя с командой /info
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Failed to delete user message: {e}")
        
        # Получаем информацию о пользователе из базы данных
        user_data = await database.get_user(message.from_user.id)
        
        if user_data:
            info_text = f"""
            📊 Информация о вас (из базы данных):
            
            ID: {user_data['user_id']}
            Имя: {user_data['first_name']}
            Фамилия: {user_data['last_name'] or 'Не указана'}
            Username: @{user_data['username'] or 'Не указан'}
            Состояние: {user_data['state']}
            Зарегистрирован: {user_data['created_at']}
            """
        else:
            info_text = f"""
            📊 Информация о вас:
            
            ID: {message.from_user.id}
            Имя: {message.from_user.first_name}
            Фамилия: {message.from_user.last_name or 'Не указана'}
            Username: @{message.from_user.username or 'Не указан'}
            """
        
        # Добавляем статус админа если пользователь является админом
        if admin_manager.is_admin(message.from_user):
            info_text += "\n\n⭐ Статус: Администратор бота"
        
        await message_manager.send_or_edit_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            text=info_text
        )

    # Обработчик инлайн кнопок
    @dp.callback_query()
    async def handle_inline_buttons(callback_query: types.CallbackQuery, user_state: UserState):
        data = callback_query.data
        
        if data == "personal_cabinet":
            # Получаем информацию о пользователе
            user_data = await database.get_user(callback_query.from_user.id)
            
            cabinet_text = f"""
            👤 Личный кабинет
            
            📋 Ваши данные:
            ID: {callback_query.from_user.id}
            Имя: {callback_query.from_user.first_name}
            Фамилия: {callback_query.from_user.last_name or 'Не указана'}
            Username: @{callback_query.from_user.username or 'Не указан'}
            """
            
            if user_data:
                cabinet_text += f"""
            Состояние: {user_data['state']}
            Зарегистрирован: {user_data['created_at'].strftime('%d.%m.%Y %H:%M')}
                """
            
            if admin_manager.is_admin(callback_query.from_user):
                cabinet_text += "\n\n⭐ Статус: Администратор бота"
            
            await message_manager.send_or_edit_message(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=cabinet_text,
                reply_markup=get_personal_cabinet_keyboard()
            )
            
        elif data == "user_stats":
            # Получаем статистику
            users = await database.get_all_users()
            users_count = await database.get_users_count()
            
            stats_text = f"""
            📊 Статистика
            
            👥 Всего пользователей: {users_count}
            """
            
            if users:
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
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=stats_text,
                reply_markup=get_back_to_cabinet_keyboard()
            )
            
        elif data == "about_project":
            about_text = "ℹ️ О проекте\n\nПозже тут появится информация о проекте"
            await message_manager.send_or_edit_message(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=about_text,
                reply_markup=get_back_to_main_keyboard()
            )
            
        elif data == "back_to_main":
            # Возвращаемся в главное меню
            is_admin_user = admin_manager.is_admin(callback_query.from_user)
            welcome_message = await get_welcome_message(callback_query.from_user, is_admin_user)
            
            # Используем обновленную клавиатуру с проверкой админских прав
            await message_manager.send_or_edit_message(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=welcome_message,
                reply_markup=get_main_inline_keyboard(is_admin_user)
            )
            
        elif data == "back_to_cabinet":
            # Возвращаемся в личный кабинет
            user_data = await database.get_user(callback_query.from_user.id)
            
            cabinet_text = f"""
            👤 Личный кабинет
            
            📋 Ваши данные:
            ID: {callback_query.from_user.id}
            Имя: {callback_query.from_user.first_name}
            Фамилия: {callback_query.from_user.last_name or 'Не указана'}
            Username: @{callback_query.from_user.username or 'Не указан'}
            """
            
            if user_data:
                cabinet_text += f"""
            Состояние: {user_data['state']}
            Зарегистрирован: {user_data['created_at'].strftime('%d.%m.%Y %H:%M')}
                """
            
            if admin_manager.is_admin(callback_query.from_user):
                cabinet_text += "\n\n⭐ Статус: Администратор бота"
            
            await message_manager.send_or_edit_message(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=cabinet_text,
                reply_markup=get_personal_cabinet_keyboard()
            )
        
        # Админские инлайн кнопки
        elif data == "admin_all_users":
            if not admin_manager.is_admin(callback_query.from_user):
                await callback_query.answer("⛔ У вас нет прав доступа")
                return
            
            # Создаем временное сообщение для передачи в admin_manager
            temp_message = types.Message(
                message_id=callback_query.message.message_id,
                from_user=callback_query.from_user,
                chat=callback_query.message.chat,
                date=callback_query.message.date,
                text=""
            )
            
            await admin_manager.show_all_users(temp_message, message_manager, get_admin_back_keyboard())
            
        elif data == "admin_stats":
            if not admin_manager.is_admin(callback_query.from_user):
                await callback_query.answer("⛔ У вас нет прав доступа")
                return
            
            # Создаем временное сообщение для передачи в admin_manager
            temp_message = types.Message(
                message_id=callback_query.message.message_id,
                from_user=callback_query.from_user,
                chat=callback_query.message.chat,
                date=callback_query.message.date,
                text=""
            )
            
            await admin_manager.show_admin_stats(temp_message, message_manager, get_admin_back_keyboard())
            
        elif data == "admin_back_to_main":
            if not admin_manager.is_admin(callback_query.from_user):
                await callback_query.answer("⛔ У вас нет прав доступа")
                return
            
            # Возвращаем в основное состояние
            await database.set_user_state(callback_query.from_user.id, UserState.MAIN)
            
            # Показываем обновленное приветственное сообщение с учетом админских прав
            is_admin_user = admin_manager.is_admin(callback_query.from_user)
            welcome_message = await get_welcome_message(callback_query.from_user, is_admin_user)
            
            # Важно: передаем is_admin_user в клавиатуру
            await message_manager.send_or_edit_message(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=welcome_message,
                reply_markup=get_main_inline_keyboard(is_admin_user)
            )
            
        elif data == "admin_back_to_main_menu":
            if not admin_manager.is_admin(callback_query.from_user):
                await callback_query.answer("⛔ У вас нет прав доступа")
                return
            
            # Возвращаемся в главное меню админки
            admin_text = """
            🛠️ Админ панель
            
            Доступные функции:
            • Просмотр всех пользователей
            • Статистика бота
            
            Используйте кнопки ниже для управления!
            """
            await message_manager.send_or_edit_message(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=admin_text,
                reply_markup=get_admin_main_keyboard()
            )
        elif data == "admin_panel":
            if not admin_manager.is_admin(callback_query.from_user):
                await callback_query.answer("⛔ У вас нет прав доступа")
                return
            
            # Устанавливаем состояние админа
            await database.set_user_state(callback_query.from_user.id, UserState.ADMIN)
            
            admin_text = """
            🛠️ Админ панель
            
            Доступные функции:
            • Просмотр всех пользователей
            • Статистика бота
            
            Используйте кнопки ниже для управления!
            """
            await message_manager.send_or_edit_message(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                text=admin_text,
                reply_markup=get_admin_main_keyboard()
            )
        
        await callback_query.answer()

    # Обработчик любого текстового сообщения
    @dp.message()
    async def echo_message(message: types.Message, user_state: UserState):
        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Failed to delete user message: {e}")
            
        if user_state == UserState.MAIN:
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text=f"Вы сказали: {message.text}"
            )
        else:
            await message_manager.send_or_edit_message(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                text="ℹ️ Используйте доступные команды или кнопки"
            )

    # Запускаем бота
    try:
        print("✅ Бот запускается...")
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
    finally:
        # Закрываем соединение с базой данных при завершении
        await database.close()
        print("✅ Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())