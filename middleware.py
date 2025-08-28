from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
from database import UserState

class UserStateMiddleware(BaseMiddleware):
    def __init__(self, database):
        self.database = database
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Получаем состояние пользователя из базы данных
            user_state = await self.database.get_user_state(event.from_user.id)
            data['user_state'] = user_state
        except Exception as e:
            # В случае ошибки используем состояние по умолчанию
            data['user_state'] = UserState.MAIN
            print(f"Error getting user state: {e}")
        
        # Вызываем следующий обработчик
        return await handler(event, data)