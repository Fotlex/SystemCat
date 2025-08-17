from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from panel.models import Order


WINDOW_TYPE_TO_FIELD_MAP = {
    'ПВХ': 'type_1_count',
    'Фасад': 'type_2_count',
    'Деревянные': 'type_3_count',
    'Раздвижные': 'type_4_count',
}

FIELD_TO_WINDOW_TYPE_MAP = {v: k for k, v in WINDOW_TYPE_TO_FIELD_MAP.items()}


PRODUCT_NAME_TO_KEY = {
    'Решетка на замках': 'type_1',
    'Решетка на шпингалете': 'type_2',
    'Вольер': 'type_3',
    'Ограничитель': 'type_4',
    'Дверь': 'type_5',
    'Нестандарт(На барашках)': 'type_6',
}


def get_order_composition_text(order: Order) -> str:
    composition_parts = []
    
    for field_name, label in FIELD_TO_WINDOW_TYPE_MAP.items():
        count = getattr(order, field_name)
        
        if count > 0:
            composition_parts.append(f"• {label} - {count} шт.")
            
    if not composition_parts:
        return "В заказе пока нет изделий."
        
    return "Текущий состав заказа:\n" + "\n".join(composition_parts)


async def get_order_types_text(order: Order):
    items = [item async for item in order.items.all()]

    if not items:
        return "Состав заказа пока не определен."

    lines = []
    grand_total = 0

    for i, item in enumerate(items, 1):
        item_subtotal = item.price * item.quantity
        
        grand_total += item_subtotal

        item_description = (
            f"{i}. {item.get_product_type_display()}\n"
            f"   - Размер: {item.size}\n"
            f"   - Цвет: {item.color}\n"
            f"   - Цена за шт.: {item.price:.2f} руб.\n"
            f"   - Количество: {item.quantity} шт.\n"
            f"   - Итого по позиции: {item_subtotal:.2f} руб."
        )
        lines.append(item_description)


    return "\n\n".join(lines)


async def get_order_composition_text_for_workshop(order: Order) -> str:
    items = [item async for item in order.items.all()]

    if not items:
        return "Состав заказа пока не определен."

    lines = []

    for i, item in enumerate(items, 1):
        item_description = (
            f"{i}. {item.get_product_type_display()}\n"
            f"   - Размер: {item.size}\n"
            f"   - Цвет: {item.color}\n"
            f"   - Количество: {item.quantity} шт."
        )
        lines.append(item_description)

    return "\n\n".join(lines)


async def delete_previous_order_messages(bot: Bot, order: Order):
    messages_info = order.active_messages_info
    
    await delete_previous_order_messages_bd(bot, order)
    
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
                
                
async def delete_previous_order_messages_bd(bot: Bot, order: Order):
    active_messages = [msg async for msg in order.active_telegram_messages.all()]
    
    messages_by_chat = {}
    for msg_entry in active_messages:
        if msg_entry.chat_id not in messages_by_chat:
            messages_by_chat[msg_entry.chat_id] = []
        messages_by_chat[msg_entry.chat_id].append(msg_entry.msg_id)
    
    deleted_db_ids = [] 

    for chat_id, message_ids in messages_by_chat.items():
        if chat_id and message_ids:
            try:
                await bot.delete_messages(
                    chat_id=chat_id,
                    message_ids=message_ids
                )
                
                for msg_entry in active_messages:
                    if msg_entry.chat_id == chat_id and msg_entry.msg_id in message_ids:
                        deleted_db_ids.append(msg_entry.id)
            except TelegramBadRequest as e:
                for msg_entry in active_messages:
                    if msg_entry.chat_id == chat_id and msg_entry.msg_id in message_ids:
                        deleted_db_ids.append(msg_entry.id)
                print(f"Ошибка Telegram при удалении сообщений {message_ids} в чате {chat_id}: {e}")
            except Exception as e:
                print(f"Неожиданная ошибка при удалении сообщений {message_ids} в чате {chat_id}: {e}")

    if deleted_db_ids:
        await order.active_telegram_messages.all().adelete()
        print(f"Удалены записи ActiveMessage для заказа {order.id}.")
    else:
        print(f"Нет записей ActiveMessage для удаления из БД для заказа {order.id}.")