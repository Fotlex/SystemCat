from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder

from panel.models import User, Order, Client, OrderPhoto 
from admin_bot.keyboards import *
from admin_bot.states import DateClient
from config import config

WINDOW_TYPE_MAP = {value: key for key, value in Order.WINDOW_TYPE_CHOICES}
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    if not user.role and user.role not in ['A', 'B']:
        await message.answer(text='У вас не подходящая роль, или же она отсутствует')
        return
    
    await message.answer(
        text='Здравствуйте!',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='СОЗДАТЬ ЗАКАЗ', callback_data='start_order')],
        ])
    )
    
    
@router.callback_query(F.data == 'start_order')
async def f(callback: CallbackQuery):
    await callback.message.edit_text(
        text='Какой тип заказа?',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='На замер', callback_data='type_measurement')],
            [InlineKeyboardButton(text='Самостоятельный замер', callback_data='type_delivery')],
        ])
    )
    
    
@router.callback_query(F.data.startswith('type_'))
async def process_order_type(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')
    type = callback.data.split('_')[1]
    
    order = await Order.objects.acreate(
        order_type=type
    )
    
    await state.update_data(order_id=order.id)
    
    if type == 'measurement':
        await callback.message.answer(
            text='ГОРОД/МЕЖГОРОД',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Санкт-Петербург', callback_data='measurement_city')],
            ])
        )
        return
    
    
    await callback.message.answer(
        text='Выберете тип изделия: ',
        reply_markup=ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text='Решетка на замках')],
            [KeyboardButton(text='Решетка на шпингалете')],
            [KeyboardButton(text='Вольер')],
            [KeyboardButton(text='Ограничитель')],
            [KeyboardButton(text='Дверь')],
            [KeyboardButton(text='Нестандарт(На барашках)')],
        ])
    )
    
    await state.set_state(DateClient.wait_type)
    

@router.callback_query(F.data.startswith('measurement_'))
async def f(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    order.subtype = callback.data.split('_')[1]
    
    await order.asave()
    
    await callback.message.answer(
        text='Выберете тип изделия: ',
        reply_markup=ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text='Решетка на замках')],
            [KeyboardButton(text='Решетка на шпингалете')],
            [KeyboardButton(text='Вольер')],
            [KeyboardButton(text='Ограничитель')],
            [KeyboardButton(text='Дверь')],
            [KeyboardButton(text='Нестандарт(На барашках)')],
        ])
    )
    
    await state.set_state(DateClient.wait_type)
    
    
@router.message(F.text, DateClient.wait_type)
async def type_client(message: Message, state: FSMContext):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    window_type_key = WINDOW_TYPE_MAP.get(message.text)
    if not window_type_key:
        await message.answer(
            text="Пожалуйста, выберите один из предложенных вариантов, используя кнопки.",
            reply_markup=ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text='Решетка на замках')],
                [KeyboardButton(text='Решетка на шпингалете')],
                [KeyboardButton(text='Вольер')],
                [KeyboardButton(text='Ограничитель')],
                [KeyboardButton(text='Дверь')],
                [KeyboardButton(text='Нестандарт(На барашках)')],
            ])
        )
        return
    
    
    order.window_type = window_type_key
    await order.asave()
    
    await message.answer(
        text='Начнем ввод данных клиента.\nВведите его ФИО',
        reply_markup=None
    )
    
    await state.set_state(DateClient.wait_name)
    

@router.message(F.text, DateClient.wait_name)
async def f(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(DateClient.wait_phone)
    
    await message.answer(text='Введите номер телефона клиента', reply_markup=None)
    
    
@router.message(F.text, DateClient.wait_phone)
async def f(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(DateClient.wait_cost)
    
    await message.answer(text='Введите стоимость: ')


@router.message(F.text, DateClient.wait_cost)
async def f(message: Message, state: FSMContext):
    await state.update_data(cost=message.text)
    await state.set_state(DateClient.wait_address)
    
    await message.answer(text='Введите адрес клиента')

    
@router.message(F.text, DateClient.wait_address)
async def f(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    
    data = await state.get_data()
    
    client, created = await Client.objects.aget_or_create(
        phone_number=data.get('phone'),
        name=data.get('name'),
        address=data.get('address'),
    )
    
    order = await Order.objects.aget(id=data.get('order_id'))
    order.client = client
    await order.asave()
    capture = ''
    if order.order_type == 'measurement':
        capture = f'#{order.get_order_type_display()}\nЗаказ №{order.id}\nО клинте:\nНомер телефона: {client.phone_number}.\nАдрес: {client.address}\nФИО: {client.name}\nСтоимость замера: {data.get('cost')}\nТип изделия: {order.get_window_type_display()}'
        order.measurement_cost = data.get('cost')
        await order.asave()
    else:
        capture = f'#{order.get_order_type_display()}\nЗаказ №{order.id}\nО клинте:\nНомер телефона: {client.phone_number}.\nАдрес: {client.address}\nФИО: {client.name}\nСтоимость изделия: {data.get('cost')}\nТип изделия: {order.get_window_type_display()}'

    await state.update_data(capture=capture)
    
    if order.order_type != 'measurement':
        try:
            await message.answer(
                text=capture,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Добавить фото/Скриншот', callback_data=f'admin_add_photo:{order.id}')],
                    [InlineKeyboardButton(text='Отправить в цех', callback_data=f'admin_to_chat:{order.id}')],
                ])
            )
        except Exception as e:
            await message.answer('Что-то не так с введеными данными о клиенте, попробуйте снова')
            await state.clear()
    else:
        try:
            await message.answer(
                text=capture,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Отправить на замер', callback_data=f'admin_to_chat_2:{order.id}')],
                ])
            )
        except Exception as e:
            await message.answer('Что-то не так с введеными данными о клиенте, попробуйте снова')
            await state.clear()


@router.callback_query(F.data.startswith('admin_to_chat_2:'))
async def chat1(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    capture = data.get('capture')
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    order.current_caption = capture
    await bot.send_message(
        chat_id=config.CHAT1_ID,
        text=capture,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Принять замер', callback_data=f'take_zamer:{order_id}')],
            [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
        ])
    )
    chat = await bot.get_chat(chat_id=config.CHAT1_ID)
    chat_title = chat.title
    order.status = 'sent_to_size'
    order.chat_location = chat_title
    await order.asave()
    
    await callback.message.edit_text(f"Заказ №{order.id} успешно отправлен на замер.")
    
    await state.clear()

@router.callback_query(F.data.startswith('admin_to_chat:'))
async def send_order_to_workshop(callback: CallbackQuery, bot: Bot, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    data = await state.get_data()
    
    try:
        order = await Order.objects.select_related('client').aget(id=order_id)
        client = order.client
        photos = [p async for p in order.photos.all()]

        if not photos:
            await callback.answer(
                "К заказу не приложены фотографии. Пожалуйста, сначала добавьте их.",
                show_alert=True
            )
            return

        caption = f"#{order.get_order_type_display()}\nЗаказ №{order.id}\nО клинте:\nНомер телефона: {client.phone_number}.\nАдрес: {client.address}\nФИО: {client.name}\nСтоимость изделия: {data.get('cost')}"
        order.current_caption = caption
        media_group = MediaGroupBuilder(caption=caption)
        for photo_object in photos:
            media_group.add_photo(media=photo_object.file_id)
        
        await bot.send_media_group(
            chat_id=config.CHAT4_ID,
            media=media_group.build(),
        )
        await bot.send_message(
            chat_id=config.CHAT4_ID,
            text=f"Действия для заказа №{order_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='В работу', callback_data=f'in_work:{order_id}')],
                [InlineKeyboardButton(text='Выполнен', callback_data=f'compleate_4:{order_id}')],
                [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
            ])
        )
        
        
        chat = await bot.get_chat(chat_id=config.CHAT4_ID)
        chat_title = chat.title
        order.chat_location = chat_title
        order.status = 'sent_to_workshop'
        await callback.message.edit_text(f"Заказ №{order.id} успешно отправлен в цех.")
        await order.asave()
        await state.clear()
        
    except Exception as e:
        print(f"Произошла ошибка при отправке: {e}")
        await callback.message('Произошла ошибка, попробуйте создать заказ снова')
       
        
@router.callback_query(F.data.startswith('admin_add_photo:'))
async def photo_send(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id_for_photo=order_id)
    
    await callback.message.answer(
        text='Отправьте 1 или несколько фото: '
    )
    await state.set_state(DateClient.wait_photo)
    await callback.answer('')
    
    
@router.message(DateClient.wait_photo)
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
        await message.answer(f"Не удалось сохранить фото. Ошибка: {e}")
        return

    if saved_photos_count == len(messages_to_process):
        await message.answer(f"Добавлено к заказу: {saved_photos_count} фото.")
    