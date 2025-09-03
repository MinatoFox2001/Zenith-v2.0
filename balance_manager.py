from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class BalanceManager:
    def __init__(self, database):
        self.database = database

    def get_balance_keyboard(self):
        """Клавиатура для управления балансом"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance_deposit")],
                [InlineKeyboardButton(text="📊 История операций", callback_data="balance_history")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_cabinet")]
            ]
        )

    def get_deposit_keyboard(self):
        """Клавиатура для пополнения баланса"""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💎 Пополнить бонусы", callback_data="deposit_bonus")],
                [InlineKeyboardButton(text="💵 Пополнить рубли", callback_data="deposit_rubles")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="balance_back")]
            ]
        )

    async def show_balance(self, user_id: int, chat_id: int, message_manager):
        """Показать баланс пользователя"""
        try:
            bonus_balance = await self.database.get_balance(user_id, 'bonus')
            rubles_balance = await self.database.get_balance(user_id, 'rubles')
            
            balance_text = f"""
            💰 Ваши балансы:

            💎 Бонусные баллы: {bonus_balance:.2f}
            💵 Рубли: {rubles_balance:.2f}

            💡 Вы можете пополнить баланс или посмотреть историю операций.
            """
            
            await message_manager.send_or_edit_message(
                chat_id=chat_id,
                user_id=user_id,
                text=balance_text,
                reply_markup=self.get_balance_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error showing balance: {e}")
            await message_manager.send_or_edit_message(
                chat_id=chat_id,
                user_id=user_id,
                text="❌ Ошибка при получении баланса"
            )

    async def deposit_balance(self, user_id: int, balance_type: str, amount: float, description: str = "Пополнение"):
        """Пополнение баланса"""
        try:
            new_balance = await self.database.update_balance(
                user_id=user_id,
                balance_type=balance_type,
                amount=amount,
                transaction_type='deposit',
                description=description
            )
            return new_balance
        except Exception as e:
            logger.error(f"Error depositing balance: {e}")
            raise

    async def withdraw_balance(self, user_id: int, balance_type: str, amount: float, description: str = "Списание"):
        """Списание с баланса"""
        try:
            current_balance = await self.database.get_balance(user_id, balance_type)
            if current_balance < amount:
                raise ValueError("Недостаточно средств")
            
            new_balance = await self.database.update_balance(
                user_id=user_id,
                balance_type=balance_type,
                amount=-amount,
                transaction_type='withdraw',
                description=description
            )
            return new_balance
        except Exception as e:
            logger.error(f"Error withdrawing balance: {e}")
            raise

    async def transfer_balance(self, from_user_id: int, to_user_id: int, balance_type: str, amount: float, description: str = "Перевод"):
        """Перевод между пользователями"""
        try:
            # Проверяем наличие средств у отправителя
            from_balance = await self.database.get_balance(from_user_id, balance_type)
            if from_balance < amount:
                raise ValueError("Недостаточно средств для перевода")
            
            # Выполняем перевод в транзакции
            async with self.database.pool.acquire() as connection:
                async with connection.transaction():
                    # Списание у отправителя
                    await self.database.update_balance(
                        user_id=from_user_id,
                        balance_type=balance_type,
                        amount=-amount,
                        transaction_type='transfer',
                        description=f"Перевод пользователю {to_user_id}: {description}"
                    )
                    
                    # Зачисление получателю
                    await self.database.update_balance(
                        user_id=to_user_id,
                        balance_type=balance_type,
                        amount=amount,
                        transaction_type='transfer',
                        description=f"Перевод от пользователя {from_user_id}: {description}"
                    )
            
            return True
        except Exception as e:
            logger.error(f"Error transferring balance: {e}")
            raise

    async def show_transaction_history(self, user_id: int, chat_id: int, message_manager, limit: int = 10):
        """Показать историю транзакций"""
        try:
            transactions = await self.database.get_transaction_history(user_id, limit)
            
            if not transactions:
                history_text = "📊 История операций пуста."
            else:
                history_text = "📊 История последних операций:\n\n"
                
                for i, transaction in enumerate(transactions, 1):
                    amount = transaction['amount']
                    sign = "+" if amount > 0 else ""
                    type_emoji = "⬆️" if amount > 0 else "⬇️"
                    
                    history_text += (
                        f"{i}. {type_emoji} {transaction['balance_type']}: {sign}{amount:.2f}\n"
                        f"   Тип: {transaction['transaction_type']}\n"
                        f"   Дата: {transaction['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
                    )
                    
                    if transaction['description']:
                        history_text += f"   Описание: {transaction['description']}\n"
                    
                    history_text += "\n"
            
            await message_manager.send_or_edit_message(
                chat_id=chat_id,
                user_id=user_id,
                text=history_text,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="balance_back")]]
                )
            )
            
        except Exception as e:
            logger.error(f"Error showing transaction history: {e}")
            await message_manager.send_or_edit_message(
                chat_id=chat_id,
                user_id=user_id,
                text="❌ Ошибка при получении истории операций"
            )