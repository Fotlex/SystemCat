from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.exceptions import TelegramBadRequest

from panel.models import User, Order, OrderItem, OrderPhoto 
from admin_bot.keyboards import *
from admin_bot.states import WorkStates, AddItemFSM
from admin_bot.utils import *
from config import config


router = Router()


@router.callback_query(F.data.startswith('cancel:'))
async def cans(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id=order_id)

    await callback.message.edit_text('Введите причину отмены: ')
    await state.set_state(WorkStates.wait_cansel_reason)


@router.message(F.text, WorkStates.wait_cansel_reason)
async def cans_comment(message: Message, state: FSMContext, user: User, bot: Bot):
    data = await state.get_data()

    order = await Order.objects.aget(id=int(data.get('order_id')))
    order.status = 'canceled'
    order.cancellation_user = user
    order.cancellation_reason = message.text
    await delete_previous_order_messages(bot, order)
    await message.delete()
    await order.asave()

    await message.answer(f'Заказ №{order.id} отменен')



@router.callback_query(F.data.startswith('take_zamer:'))
async def cans(callback: CallbackQuery, user: User, bot: Bot):
    order_id = int(callback.data.split(':')[1])

    order = await Order.objects.aget(id=order_id)
    order.current_caption = callback.message.text
    
    await bot.send_message(
        chat_id=user.id,
        text=callback.message.text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Завершить', callback_data=f'driver_to_men:{order_id}')],
            [InlineKeyboardButton(text='Добавить фото замера', callback_data=f'driver_add_photo:{order_id}')],
            [InlineKeyboardButton(text='Внести замер как текст', callback_data=f'driver_add_text:{order_id}')],
            [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
            [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
        ])
    )
    order.chat_location = None
    order.responsible_employee = user
    await order.asave()
    await callback.message.delete()
    await callback.answer('')

    
@router.callback_query(F.data.startswith('driver_to_men:'))
async def send_order_to_workshop(callback: CallbackQuery, bot: Bot, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    data = await state.get_data()
    order = await Order.objects.select_related('client').aget(id=order_id)
    try:
        client = order.client
        photos = [p async for p in order.photos.all()]

        if not photos:
            await callback.answer(
                "К заказу не приложены фотографии. Пожалуйста, сначала добавьте их.",
                show_alert=True
            )
            return

        caption = order.current_caption
        
        media_group = MediaGroupBuilder(caption=caption)
        for photo_object in photos:
            media_group.add_photo(media=photo_object.file_id)
        
        sent_media_messages = await bot.send_media_group(
            chat_id=config.CHAT3_ID,
            media=media_group.build(),
        )
        sent_action_message = await bot.send_message(
            chat_id=config.CHAT3_ID,
            text=f"Действия для заказа №{order_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Добавить статус оплаты', callback_data=f'add_pay_status:{order_id}')],
                [InlineKeyboardButton(text='Отправить в цех', callback_data=f'send_work_place:{order_id}')],
                [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
                [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
            ])
        )

        new_message_ids = [m.message_id for m in sent_media_messages]
        new_message_ids.append(sent_action_message.message_id)


        order.active_messages_info = {
            "chat_id": config.CHAT3_ID,
            "message_ids": new_message_ids,
        }

        order.responsible_employee = None
        chat = await bot.get_chat(chat_id=config.CHAT3_ID)
        chat_title = chat.title
        order.chat_location = chat_title
        await order.asave()
        await state.clear()
        await callback.message.delete()
        
    except Exception as e:
        print(f"Произошла ошибка при отправке: {e}")
        await callback.message('Произошла ошибка, попробуйте создать заказ снова')

    await callback.answer('')


async def finalize_and_send_to_workshop(order_id: int, bot: Bot, chat_id_to_send: str | int):
    order = await Order.objects.select_related('client').prefetch_related('photos', 'items').aget(id=order_id)
    client = order.client
    
    
    products_text = await get_order_composition_text_for_workshop(order) 
        
    caption = f"#{order.get_order_type_display()} - Заказ №{order.id}\n\n" \
              f"Клиент: {client.name}\n" \
              f"Телефон: {client.phone_number}\n" \
              f"Адрес: {client.address}\n\n" \
              f"Состав заказа:\n{products_text}\n"
    
    if order.comments:
        caption += f"Комментарии: {order.comments}\n"
        
    media_group = MediaGroupBuilder(caption=caption)
    photos = [p async for p in order.photos.all()]
    for photo_object in photos:
        media_group.add_photo(media=photo_object.file_id)

    await delete_previous_order_messages(bot, order)

    sent_media_messages = await bot.send_media_group(
        chat_id=chat_id_to_send,
        media=media_group.build(),
    )
    sent_action_message = await bot.send_message(
        chat_id=chat_id_to_send,
        text=f"Действия для заказа №{order_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='В работу', callback_data=f'in_work:{order_id}')],
            [InlineKeyboardButton(text='Добавить комментарий', callback_data=f'add_comment:{order.id}')],
            [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
        ])
    )

    new_message_ids = [m.message_id for m in sent_media_messages]
    new_message_ids.append(sent_action_message.message_id)

    order.active_messages_info = {
        "chat_id": chat_id_to_send,
        "message_ids": new_message_ids,
    }
    chat = await bot.get_chat(chat_id=chat_id_to_send)
    order.status = 'sent_to_workshop'
    order.chat_location = chat.title
    order.responsible_employee = None
    await order.asave()


@router.callback_query(F.data.startswith('add_pay_status:'))
async def add_pay_status_f(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id=order_id)
    
    await callback.message.answer('Введите статус оплаты: ')
    await state.set_state(AddItemFSM.wait_status)
    
    
@router.message(F.text, AddItemFSM.wait_status)
async def remember_status(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    
    order = await Order.objects.aget(id=order_id)
    order.genral_cost_info = message.text
    await order.asave()
    
    await message.delete()
    await message.answer('Статус оплаты сохранен')
    await state.clear()
    
    


@router.callback_query(F.data.startswith('send_work_place:'))
async def send_work_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    

    if await OrderItem.objects.filter(order_id=order_id).aexists():
        await callback.answer("Отправляем заказ в цех...")
        await finalize_and_send_to_workshop(order_id, bot, config.CHAT4_ID)
        await state.clear()
        return


    await state.update_data(order_id=order_id)
    
    await callback.message.answer(
        'Начнем добавление изделий в заказ.\n\nВыберите тип первого изделия:',
        reply_markup=window_style_keyboard
    )
    await state.set_state(AddItemFSM.wait_product_type)
    await callback.answer()


@router.message(AddItemFSM.wait_product_type, F.text.in_(PRODUCT_NAME_TO_KEY.keys()))
async def process_product_type(message: Message, state: FSMContext):
    product_key = PRODUCT_NAME_TO_KEY[message.text]
    await state.update_data(product_type=product_key)
    
    await message.answer("Принято. Теперь введите размер изделия (например, 154*46*16):")
    await state.set_state(AddItemFSM.wait_size)


@router.message(AddItemFSM.wait_size)
async def process_size(message: Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("Отлично. Введите цвет изделия:")
    await state.set_state(AddItemFSM.wait_color)


@router.message(AddItemFSM.wait_color)
async def process_color(message: Message, state: FSMContext):
    await state.update_data(color=message.text)
    await message.answer("Хорошо. Теперь введите цену за *одну единицу* этого изделия (только число):")
    await state.set_state(AddItemFSM.wait_price)


@router.message(AddItemFSM.wait_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Цена должна быть числом. Пожалуйста, попробуйте еще раз.")
        return
        
    await state.update_data(price=price)
    await message.answer("И последнее: введите **количество** изделий с этими параметрами:")
    await state.set_state(AddItemFSM.wait_quantity)


@router.message(AddItemFSM.wait_quantity)
async def process_quantity_and_save(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Пожалуйста, введите корректное число (например, 1, 2, 5).")
        return
        
    
    data = await state.get_data()
    
    
    new_item = await OrderItem.objects.acreate(
        order_id=data['order_id'],
        product_type=data['product_type'],
        size=data['size'],
        color=data['color'],
        price=data['price'],
        quantity=int(message.text) 
    )
    
    item_info = (
        f"Тип: {new_item.get_product_type_display()}\n"
        f"Размер: {new_item.size}\n"
        f"Цвет: {new_item.color}\n"
        f"Цена: {new_item.price} руб/шт.\n"
        f"Количество: {new_item.quantity} шт."
    )

    await message.answer(
        f"✅ Позиция добавлена в заказ:\n\n{item_info}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить еще позицию", callback_data=f"add_another_item:{data['order_id']}")],
            [InlineKeyboardButton(text="➡️ Завершить и отправить в цех", callback_data=f"finish_and_send:{data['order_id']}")]
        ])
    )
    
    await state.set_state(AddItemFSM.wait_for_next_action)


@router.callback_query(AddItemFSM.wait_for_next_action, F.data.startswith('add_another_item:'))
async def add_another_item(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        'Выберите тип следующего изделия:', 
        reply_markup=window_style_keyboard
    )
    await state.set_state(AddItemFSM.wait_product_type)
    await callback.answer()
    
@router.callback_query(AddItemFSM.wait_for_next_action, F.data.startswith('finish_and_send:'))
async def finish_and_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    await callback.message.edit_text("Отлично! Формирую и отправляю заказ в цех...")
    
    await finalize_and_send_to_workshop(order_id, bot, config.CHAT4_ID)
    
    await callback.answer("Заказ успешно отправлен!", show_alert=True)
    await state.clear()


@router.message(F.text, WorkStates.wait_cost)
async def set_cost(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    order = await Order.objects.aget(id=order_id)

    order.genral_cost_info = message.text
    order.current_caption += f'\n\nРасчет:\n{message.text}\n\n'

    await order.asave()
    await message.answer('Стоимость добавлена, можете отправлять заказ в цех')
    await state.clear()
    


@router.callback_query(F.data.startswith('driver_add_photo:'))
async def photo_add(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id_for_photo=order_id)
    await callback.message.answer('Отправьте 1 или несколько фото/скриншотов')

    await state.set_state(WorkStates.wait_photo)
    await callback.answer('')


@router.message(WorkStates.wait_photo)
async def album_and_photo_save_to_db(message: Message, state: FSMContext, album: list[Message] | None = None):
    data = await state.get_data()
    order_id = data.get('order_id_for_photo')

    if not order_id:
        await message.answer("Произошла ошибка, не могу определить для какого заказа это фото. Пожалуйста, начните заново, нажав 'Добавить фото' у нужного заказа.")
        await state.clear()
        return

    messages_to_process = album or [message]

    saved_photos_count = 0
    try:
        order = await Order.objects.aget(id=order_id)

        for msg in messages_to_process:
            if msg.photo:
                await OrderPhoto.objects.acreate(
                    order=order,
                    file_id=msg.photo[-1].file_id
                )
                saved_photos_count += 1
            
    except Order.DoesNotExist:
        await message.answer(f"Заказ с ID {order_id} не найден. Произошла ошибка.")
        await state.clear()
        return
    except Exception as e:
        print(f"Ошибка при сохранении фото: {e}") 
        return

    if saved_photos_count == len(messages_to_process):
        await message.answer(f"Добавлено к заказу: {saved_photos_count} фото.")


@router.callback_query(F.data.startswith('driver_add_text:'))
async def mess_size(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id=order_id)

    await callback.message.answer('Отправьте замер одним сообщением')
    await state.set_state(WorkStates.wait_text_size)
    await callback.answer('')


@router.message(F.text, WorkStates.wait_text_size)
async def mess(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    order = await Order.objects.aget(id=order_id)

    order.sizes = message.text
    await order.asave()
    try:
        order.current_caption += f'\n\nДобавленный замер: \n{message.text}\n\n'
        await order.asave()

        await message.answer('Текст замера успешно добавлен')
    except Exception as e:
        print(e)


@router.callback_query(F.data.startswith('in_work:'))
async def choise_worker(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id=order_id)

    await callback.message.edit_text(
        text=f'Выберете ответственного для заказа №{order_id}',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Стол 1', callback_data='table_first')],
            [InlineKeyboardButton(text='Стол 2', callback_data='table_second')],
            [InlineKeyboardButton(text='Стол 3', callback_data='table_thirt')],
        ])
    )
    await callback.answer('')


@router.callback_query(F.data.startswith('table_'))
async def work(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    order = await Order.objects.aget(id=order_id)

    worker = callback.data.split('_')[1]
    order.current_work_place = worker
    
    await order.asave()

    await callback.message.edit_text(
        text=f'Заказ №{order_id} в работе: {order.get_current_work_place_display()}',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
            [InlineKeyboardButton(text='Завершить', callback_data=f'go_5_chat:{order_id}')],
        ])
    )
    await callback.answer('')


@router.callback_query(F.data.startswith('go_5_chat:'))
async def work(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.select_related('client').aget(id=order_id)
    client = order.client
    photos = [p async for p in order.photos.all()]

    products_text = await get_order_types_text(order)
    caption = f"#{order.get_order_type_display()} - Заказ №{order.id}\n\n" \
              f"Клиент: {client.name}\n" \
              f"Телефон: {client.phone_number}\n" \
              f"Адрес: {client.address}\n\n" \
              f"Состав заказа:\n{products_text}\n"
    
    if order.comments:
        caption += f"Комментарии: {order.comments}\n"

    order.current_caption = caption
    await order.asave()
    
    media_group = MediaGroupBuilder(caption=caption)
    for photo_object in photos:
        media_group.add_photo(media=photo_object.file_id)

    sent_media_messages = await bot.send_media_group(
            chat_id=config.CHAT5_ID,
            media=media_group.build(),
        )
    sent_action_message = None
    if order.order_type == 'measurement' and order.subtype == 'city':
        sent_action_message = await bot.send_message(
            chat_id=config.CHAT5_ID,
            text=f"Действия для заказа №{order_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Доставка', callback_data=f'delivery_chat1:{order_id}')],
                [InlineKeyboardButton(text='Самовывоз', callback_data=f'go_in_chat6:{order_id}')],
                [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
                [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
            ])
        )
    elif order.order_type == 'delivery':
        sent_action_message = await bot.send_message(
            chat_id=config.CHAT5_ID,
            text=f"Действия для заказа №{order_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Доставка', callback_data=f'delivery_chat1:{order_id}')],
                [InlineKeyboardButton(text='В транспортную', callback_data=f'go_in_chat7:{order_id}')],
                [InlineKeyboardButton(text='Самовывоз', callback_data=f'go_in_chat6:{order_id}')],
                [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
                [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
            ])
        )

    new_message_ids = [m.message_id for m in sent_media_messages]
    new_message_ids.append(sent_action_message.message_id)

    await delete_previous_order_messages(bot, order)

    order.active_messages_info = {
        "chat_id": config.CHAT5_ID,
        "message_ids": new_message_ids,
    }

    chat = await bot.get_chat(chat_id=config.CHAT5_ID)
    chat_title = chat.title
    order.status = 'workshop_completed'
    order.chat_location = chat_title
    order.responsible_employee = None
    await order.asave()
    await state.clear()



@router.callback_query(F.data.startswith('go_in_chat6:'))
async def chat6_f(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.select_related('client').aget(id=order_id)
    photos = [p async for p in order.photos.all()]

    caption = order.current_caption

    media_group = MediaGroupBuilder(caption=caption)
    for photo_object in photos:
        media_group.add_photo(media=photo_object.file_id)

    sent_media_messages = await bot.send_media_group(
        chat_id=config.CHAT6_ID,
        media=media_group.build(),
    )
    sent_action_message = await bot.send_message(
        chat_id=config.CHAT6_ID,
        text=f"Действия для заказа №{order_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Завершить', callback_data=f'end_order:{order_id}')],
            [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
            [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
        ])
    )

    new_message_ids = [m.message_id for m in sent_media_messages]
    new_message_ids.append(sent_action_message.message_id)

    await delete_previous_order_messages(bot, order)

    order.active_messages_info = {
        "chat_id": config.CHAT6_ID,
        "message_ids": new_message_ids,
    }

    chat = await bot.get_chat(chat_id=config.CHAT6_ID)
    chat_title = chat.title
    order.chat_location = chat_title
    order.responsible_employee = None
    await order.asave()
    await state.clear()


@router.callback_query(F.data.startswith('go_in_chat7:'))
async def chat7_f(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.select_related('client').aget(id=order_id)
    photos = [p async for p in order.photos.all()]

    caption = order.current_caption

    media_group = MediaGroupBuilder(caption=caption)
    for photo_object in photos:
        media_group.add_photo(media=photo_object.file_id)

    sent_media_messages = await bot.send_media_group(
        chat_id=config.CHAT7_ID,
        media=media_group.build(),
    )
    sent_action_message = await bot.send_message(
        chat_id=config.CHAT7_ID,
        text=f"Действия для заказа №{order_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Завершить', callback_data=f'end_order:{order_id}')],
            [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
            [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
        ])
    )

    new_message_ids = [m.message_id for m in sent_media_messages]
    new_message_ids.append(sent_action_message.message_id)

    await delete_previous_order_messages(bot, order)

    order.active_messages_info = {
        "chat_id": config.CHAT7_ID,
        "message_ids": new_message_ids,
    }

    chat = await bot.get_chat(chat_id=config.CHAT5_ID)
    chat_title = chat.title
    order.chat_location = chat_title
    order.responsible_employee = None
    await order.asave()
    await state.clear()


@router.callback_query(F.data.startswith('delivery_chat1:'))
async def chat7_f(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.select_related('client').aget(id=order_id)
    photos = [p async for p in order.photos.all()]

    caption = order.current_caption
    lines = caption.split('\n')
    lines[0] = '#Доставка'
    new_capture = '\n'.join(lines)
    order.current_caption = new_capture
    await order.asave()

    media_group = MediaGroupBuilder(caption=new_capture)
    for photo_object in photos:
        media_group.add_photo(media=photo_object.file_id)

    sent_media_messages = await bot.send_media_group(
        chat_id=config.CHAT1_ID,
        media=media_group.build(),
    )
    sent_action_message = await bot.send_message(
        chat_id=config.CHAT1_ID,
        text=f"Действия для заказа №{order_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Принять доставку', callback_data=f'take_dekivery_1:{order_id}')],
            [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
            [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
        ])
    )

    new_message_ids = [m.message_id for m in sent_media_messages]
    new_message_ids.append(sent_action_message.message_id)

    await delete_previous_order_messages(bot, order)

    order.active_messages_info = {
        "chat_id": config.CHAT1_ID,
        "message_ids": new_message_ids,
    }

    chat = await bot.get_chat(chat_id=config.CHAT5_ID)
    chat_title = chat.title
    order.chat_location = chat_title
    order.responsible_employee = None
    await order.asave()
    await state.clear()


@router.callback_query(F.data.startswith('take_dekivery_1:'))
async def chat7_f(callback: CallbackQuery, state: FSMContext, bot: Bot, user: User):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.select_related('client').aget(id=order_id)
    photos = [p async for p in order.photos.all()]

    caption = order.current_caption

    media_group = MediaGroupBuilder(caption=caption)
    for photo_object in photos:
        media_group.add_photo(media=photo_object.file_id)

    sent_media_messages = await bot.send_media_group(
        chat_id=user.id,
        media=media_group.build(),
    )
    sent_action_message = await bot.send_message(
        chat_id=user.id,
        text=f"Действия для заказа №{order_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Завершить', callback_data=f'end_driver:{order_id}')],
            [InlineKeyboardButton(text='Добавить фото', callback_data=f'end_driver_add_photo:{order_id}')],
            [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment:{order.id}')],
            [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
        ])
    )

    new_message_ids = [m.message_id for m in sent_media_messages]
    new_message_ids.append(sent_action_message.message_id)

    await delete_previous_order_messages(bot, order)

    order.active_messages_info = {
        "chat_id": user.id,
        "message_ids": new_message_ids,
    }

    order.status = 'on_delivery'
    order.chat_location = None
    order.responsible_employee = user
    await order.asave()
    await state.clear()


@router.callback_query(F.data.startswith('end_driver:'))
async def chat7_f(callback: CallbackQuery, state: FSMContext, user: User):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    await state.update_data(order_id=order_id)

    await callback.message.edit_text('Укажите способ оплаты: ')


    await state.set_state(WorkStates.end_driver)


@router.message(F.text, WorkStates.end_driver)
async def end_f(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order = await Order.objects.aget(id=int(data.get('order_id')))

    
    order.choise_pay = message.text
    order.status = 'completed'
    await order.asave()
    await delete_previous_order_messages(bot, order)
    await message.answer(f'Заказ №{order.id} завершен')
    await state.clear()
    


@router.callback_query(F.data.startswith('end_order:'))
async def chat7_f(callback: CallbackQuery, state: FSMContext, user: User, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    order.status = 'completed'
    await order.asave()
    await callback.message.edit_text(f'Заказ №{order.id} завершен')
    await delete_previous_order_messages(bot, order)
    await state.clear()


@router.callback_query(F.data.startswith('add_comment:'))
async def chat1(callback: CallbackQuery, bot: Bot, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(ord_id=order_id)
    await callback.message.answer(text='Введите коментарий к заказу: ')
    await state.set_state(WorkStates.wait_comment)


@router.message(F.text, WorkStates.wait_comment)
async def comm_f(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('ord_id')
    order = await Order.objects.aget(id=order_id)

    order.comments = f'{order.comments}\n{message.text}' if order.comments is not None else message.text

    new_comment = f'\nКоментарий: {message.text}'
    order.current_caption = f'{order.current_caption}{new_comment}' if order.current_caption is not None else f'Коментарий: {message.text}'
    await order.asave()

    await message.answer('Комментарий добавлен')
    await message.delete()
    
    
@router.callback_query(F.data.startswith('end_driver_add_photo:'))
async def chat7_f(callback: CallbackQuery, state: FSMContext, user: User):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id_for_photo=order_id)
    
    await callback.message.answer(
        text='Отправьте 1 или несколько фото: '
    )

    await state.set_state(WorkStates.wait_end_photo)
    await callback.answer('')
    
    
@router.message(WorkStates.wait_end_photo, F.photo)
async def album_and_photo_save_to_db(message: Message, state: FSMContext, album: list[Message] | None = None):
    data = await state.get_data()
    order_id = data.get('order_id_for_photo')

    if not order_id:
        await message.answer("Произошла ошибка, не могу определить для какого заказа это фото.")
        await state.clear()
        return

    messages_to_process = album or [message]

    saved_photos_count = 0
    try:
        order = await Order.objects.aget(id=order_id)

        for msg in messages_to_process:
            if msg.photo:
                await OrderPhoto.objects.acreate(
                    order=order,
                    file_id=msg.photo[-1].file_id
                )
                saved_photos_count += 1
            
    except Order.DoesNotExist:
        await message.answer(f"Заказ с ID {order_id} не найден. Произошла ошибка.")
        await state.clear()
        return
    except Exception as e:
        print(f"Ошибка при сохранении фото: {e}") 
        await message.answer(f"Не удалось сохранить фото.")
        return

    if saved_photos_count == len(messages_to_process):
        await message.answer(f"Добавлено к заказу: {saved_photos_count} фото.")