from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from panel.models import Order


WINDOW_TYPE_TO_FIELD_MAP = {
    'Решетка на замках': 'type_1_count',
    'Решетка на шпингалете': 'type_2_count',
    'Вольер': 'type_3_count',
    'Ограничитель': 'type_4_count',
    'Дверь': 'type_5_count',
    'Нестандарт(На барашках)': 'type_6_count',
}

FIELD_TO_WINDOW_TYPE_MAP = {v: k for k, v in WINDOW_TYPE_TO_FIELD_MAP.items()}


def get_order_composition_text(order: Order) -> str:
    composition_parts = []
    
    for field_name, label in FIELD_TO_WINDOW_TYPE_MAP.items():
        count = getattr(order, field_name)
        
        if count > 0:
            composition_parts.append(f"• {label} - {count} шт.")
            
    if not composition_parts:
        return "В заказе пока нет изделий."
        
    return "Текущий состав заказа:\n" + "\n".join(composition_parts)



async def delete_previous_order_messages(bot: Bot, order: Order):
    messages_info = order.active_messages_info
    
    if messages_info and "chat_id" in messages_info and "message_ids" in messages_info:
        chat_id = messages_info["chat_id"]
        message_ids = messages_info["message_ids"]
        
        if chat_id and message_ids:
            try:
                await bot.delete_messages(
                    chat_id=chat_id,
                    message_ids=message_ids
                )
            except TelegramBadRequest as e:
                print(f"Не удалось удалить сообщения {message_ids} в чате {chat_id}: {e}")