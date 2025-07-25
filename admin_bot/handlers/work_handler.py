from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.exceptions import TelegramBadRequest

from panel.models import User, Order, Client, OrderPhoto 
from admin_bot.keyboards import *
from admin_bot.states import WorkStates
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
                [InlineKeyboardButton(text='Отправить в цех', callback_data=f'send_work_place:{order_id}')],
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


@router.callback_query(F.data.startswith('send_work_place:'))
async def send_work(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    orders = await Order.objects.select_related('client').aget(id=order_id)
    photos = [p async for p in orders.photos.all()]

    caption = order.current_caption

    media_group = MediaGroupBuilder(caption=caption)
    for photo_object in photos:
        media_group.add_photo(media=photo_object.file_id)
    

    if order.product_cost:
        sent_media_messages = await bot.send_media_group(
            chat_id=config.CHAT4_ID,
            media=media_group.build(),
        )
        sent_action_message = await bot.send_message(
            chat_id=config.CHAT4_ID,
            text=f"Действия для заказа №{order_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='В работу', callback_data=f'in_work:{order_id}')],
                [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
            ])
        )

        new_message_ids = [m.message_id for m in sent_media_messages]
        new_message_ids.append(sent_action_message.message_id)

        await delete_previous_order_messages(bot, order)

        order.active_messages_info = {
            "chat_id": config.CHAT4_ID,
            "message_ids": new_message_ids,
        }


        chat = await bot.get_chat(chat_id=config.CHAT4_ID)
        chat_title = chat.title
        order.status = 'sent_to_workshop'
        order.chat_location = chat_title
        order.responsible_employee = None
        await order.asave()
        await state.clear()
        return
    
    await state.update_data(order_id=order_id)
    await callback.message.answer('Введите стоимость изделия: ')
    await state.set_state(WorkStates.wait_cost)
    await callback.answer('')


@router.message(F.text, WorkStates.wait_cost)
async def set_cost(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    order = await Order.objects.aget(id=order_id)


    try:
        order.product_cost = float(message.text)
        order.current_caption += f'\nСтоимость изделия: {order.product_cost}'

        await order.asave()
        await message.answer('Стоимость добавлена, можете отправлять заказ в цех')
        await state.clear()
    except Exception as e:
        print(e)
        await message.answer('Вы ввели некоректное число, введите число еще раз')


@router.callback_query(F.data.startswith('driver_add_photo:'))
async def photo_add(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id_for_photo=order_id)
    await callback.message.answer('Отправьте 1 или несколько фото замеров, размеры замеров тоже лучше отправлять в виде фото/скриншота')

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

    try:
        order.current_caption += f'\nДобавленный замер: \n{message.text}'
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
            [InlineKeyboardButton(text='Завершить', callback_data=f'go_5_chat:{order_id}')],
        ])
    )
    await callback.answer('')


@router.callback_query(F.data.startswith('go_5_chat:'))
async def work(callback: CallbackQuery, state: FSMContext, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.select_related('client').aget(id=order_id)
    photos = [p async for p in order.photos.all()]

    caption = order.current_caption

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

    await callback.message.edit_text('Укажите стоимость монтажа, если монтаж бесплатный, укажите 0')


    await state.set_state(WorkStates.end_driver)


@router.message(F.text, WorkStates.end_driver)
async def end_f(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order = await Order.objects.aget(id=int(data.get('order_id')))

    try:
        order.delivery_cost = float(message.text)
        order.status = 'completed'
        await order.asave()
        await delete_previous_order_messages(bot, order)
        await message.answer(f'Заказ №{order.id} завершен')
        await state.clear()
    except Exception as e:
        print(e)
        await message.answer(f'Отправленно некоректное число, попробуйте снова')


@router.callback_query(F.data.startswith('end_order:'))
async def chat7_f(callback: CallbackQuery, state: FSMContext, user: User, bot: Bot):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    order.status = 'completed'
    await order.asave()
    await callback.message.edit_text(f'Заказ №{order.id} завершен')
    await delete_previous_order_messages(bot, order)
    await state.clear()