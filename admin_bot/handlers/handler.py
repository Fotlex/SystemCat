from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder

from panel.models import User, Order, Client, OrderPhoto, OrderItem, ActiveMessage
from admin_bot.keyboards import *
from admin_bot.states import DateClient, AddItemFSMAdmin
from admin_bot.utils import *

from config import config


router = Router()


@router.message(CommandStart())
async def cmd(message: Message, user: User):
    if not user.role:
        await message.answer(text='Вы зарегестрированны в боте, но у вас нет роли, попросите администратора выдать вам роль')
        return

    await message.answer(text=f'Вы зарегестрированны в боте, ваша роль: {user.get_role_display()}')


@router.message(Command("get_id"))
async def cmd_chat_id(message: Message):
    chat_id = message.chat.id
    await message.answer(f"ID этого чата: `{chat_id}`", parse_mode="Markdown")



@router.message(Command('get_photo'))
async def get_photo_f(message: Message, user: User, state: FSMContext):
    if not user.role and user.role not in ['A', 'B']:
        await message.answer(text='У вас не подходящая роль, или же она отсутствует')
        return
    
    await message.answer('Отправьте ID(номер) заказа чьи фото вам нужно получить')
    await state.set_state(DateClient.wait_id_for_photo)


@router.message(F.text, DateClient.wait_id_for_photo)
async def take_photo_f(message: Message, state: FSMContext, bot: Bot, user: User):
    await state.clear()
    try:
        id = int(message.text)
        order = await Order.objects.aget(id=id)

        photos = [p async for p in order.photos.all()]

        if not photos:
            await message.answer(f'У заказа №{id} нет фото')
            return
        
        media_group = MediaGroupBuilder(caption=f'Фото из заказа №{id}')
        for photo_object in photos:
            media_group.add_photo(media=photo_object.file_id)

        await message.answer_media_group(media=media_group.build())

    except Order.DoesNotExist:
        await message.answer(f'Заказа с №{message.text} не существует, возможно он был удален, попробуйте еще раз введя команду заново')

    except Exception as e:
        await message.answer('Ошибка введены некоректные данные, попробуйте еще раз')
        print(e)

@router.message(Command('admin'))
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
async def process_order_type(callback: CallbackQuery, state: FSMContext, user: User):
    await callback.answer('')
    type = callback.data.split('_')[1]
    
    order = await Order.objects.acreate(
        order_type=type
    )
    
    await state.update_data(order_id=order.id)
    
    if type == 'measurement':
        await callback.message.edit_text(
            text='ГОРОД/МЕЖГОРОД',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Санкт-Петербург', callback_data='measurement_city')],
            ])
        )
        return
    
    
    msg = await callback.message.answer(
        text='Начнем ввод данных клиента.\nВведите его ФИО',
        reply_markup=None
    )
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    
    await state.set_state(DateClient.wait_name)
    await callback.message.delete()
    

@router.callback_query(F.data.startswith('measurement_'))
async def f(callback: CallbackQuery, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    order.subtype = callback.data.split('_')[1]
    
    await order.asave()
    
    if order.subtype == 'city':
        msg = await callback.message.answer(
            text='Начинаем выбор типов изделия, если их несколько выбираем по очереди, следуя инструкции.',
            reply_markup=window_type_keyboard
        )
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
        
        await state.set_state(DateClient.wait_type)
    else:
        msg = await callback.message.answer(
            text='Начнем ввод данных клиента.\nВведите его ФИО',
            reply_markup=None
        )
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
    
        await state.set_state(DateClient.wait_name)
    await callback.message.delete()
    
    
@router.message(F.text, DateClient.wait_type)
async def type_client(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    field_to_update = WINDOW_TYPE_TO_FIELD_MAP.get(message.text)

    if not field_to_update:
        msg = await message.answer(
            text="Пожалуйста, выберите один из предложенных вариантов, используя кнопки.",
            reply_markup=window_type_keyboard 
        )
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
        return
    
    current_count = getattr(order, field_to_update)
    
    setattr(order, field_to_update, current_count + 1)
    await order.asave()
    
    composition_text = get_order_composition_text(order)
    response_text = (
        f"✅ Добавлено: {message.text}\n\n"
        f"{composition_text}"
    )

    await message.answer(
        text=response_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Заполнять данные о клиенте', callback_data='go_client_data')],
            [InlineKeyboardButton(text='Добавить еще изделие', callback_data='add_more_types')],
        ])
    )
    await state.set_state(DateClient.dead_state)


@router.callback_query(F.data == 'add_more_types')
async def add_type_f(callback: CallbackQuery, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    msg = await callback.message.answer(
        text='Выберете изделие: ',
        reply_markup=window_type_keyboard
    )
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    
    await state.set_state(DateClient.wait_type)
    await callback.message.delete()


@router.callback_query(F.data == 'go_client_data')
async def data_cl_f(callback: CallbackQuery, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    msg = await callback.message.answer(
        text='Начнем ввод данных клиента.\nВведите его ФИО',
        reply_markup=None
    )
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    
    await callback.message.delete()

    await state.set_state(DateClient.wait_name)
    

@router.message(F.text, DateClient.wait_name)
async def f(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    await state.update_data(name=message.text)
    await state.set_state(DateClient.wait_phone)
    
    msg = await message.answer(text='Введите номер телефона клиента', reply_markup=None)
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    
    
@router.message(F.text, DateClient.wait_phone)
async def f(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await state.update_data(phone=message.text)
    await state.set_state(DateClient.wait_address)
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    msg = await message.answer(text='Введите адрес клиента')
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )

@router.message(F.text, DateClient.wait_address)
async def f(message: Message, state: FSMContext, user: User):
    await state.update_data(address=message.text)
    
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )

    if order.order_type == 'measurement':
        msg = await message.answer(text='Введите стоимость замера: ')
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
        await state.set_state(DateClient.wait_cost)
    else:
        msg = await message.answer(
            text='Начнем добавление изделий в заказ.\n\nВыберите тип первого изделия:',
            reply_markup=window_style_keyboard
        )
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
        await state.set_state(AddItemFSMAdmin.wait_product_type)
        
        
@router.message(AddItemFSMAdmin.wait_product_type, F.text.in_(PRODUCT_NAME_TO_KEY.keys()))
async def process_product_type(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    product_key = PRODUCT_NAME_TO_KEY[message.text]
    await state.update_data(product_type=product_key)
    
    msg = await message.answer("Принято. Теперь введите размер изделия (например, 154*46*16):")
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    await state.set_state(AddItemFSMAdmin.wait_size)


@router.message(AddItemFSMAdmin.wait_size)
async def process_size(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    await state.update_data(size=message.text)
    msg = await message.answer("Отлично. Введите цвет изделия:")
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    
    await state.set_state(AddItemFSMAdmin.wait_color)


@router.message(AddItemFSMAdmin.wait_color)
async def process_color(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    await state.update_data(color=message.text)
    msg = await message.answer("Хорошо. Теперь введите цену за одну единицу этого изделия (только число):")
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    
    await state.set_state(AddItemFSMAdmin.wait_price)


@router.message(AddItemFSMAdmin.wait_price)
async def process_price(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    try:
        price = float(message.text.replace(',', '.'))
    except ValueError:
        msg = await message.answer("Цена должна быть числом. Пожалуйста, попробуйте еще раз.")
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
        return
        
    await state.update_data(price=price)
    mes = await message.answer("И последнее: введите количество изделий с этими параметрами:")
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=mes.message_id
    )
    await state.set_state(AddItemFSMAdmin.wait_quantity)


@router.message(AddItemFSMAdmin.wait_quantity)
async def process_quantity_and_save(message: Message, state: FSMContext, bot: Bot, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    if not message.text.isdigit() or int(message.text) <= 0:
        msg = await message.answer("Пожалуйста, введите корректное число (например, 1, 2, 5).")
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
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
            [InlineKeyboardButton(text="➕ Добавить еще позицию", callback_data=f"add_another_item_adm:{data['order_id']}")],
            [InlineKeyboardButton(text="Все изделия добавлены", callback_data=f"add_all_types_adm:{data['order_id']}")]
        ])
    )
    
    await state.set_state(AddItemFSMAdmin.wait_for_next_action)


@router.callback_query(AddItemFSMAdmin.wait_for_next_action, F.data.startswith('add_another_item_adm:'))
async def add_another_item(callback: CallbackQuery, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    
    await callback.message.delete()
    msg = await callback.message.answer(
        'Выберите тип следующего изделия:', 
        reply_markup=window_style_keyboard
    )
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    await state.set_state(AddItemFSMAdmin.wait_product_type)
    await callback.answer()
    
    
@router.callback_query(AddItemFSMAdmin.wait_for_next_action, F.data.startswith('add_all_types_adm:'))
async def add_another_item(callback: CallbackQuery, state: FSMContext, user: User):
    await callback.message.delete()
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
    
    products_text = await get_order_types_text(order)
    capture = (
        f"#{order.get_order_type_display()}\n"
        f"Заказ №{order.id}\n"
        f"Адрес: {client.address}\n"
        f"Номер телефона: {client.phone_number}\n"
        f"ФИО: {client.name}\n"
        f"{products_text}" 
    )
    await state.update_data(capture=capture)
    
    order.current_caption = capture
    order.genral_cost_info = '100%'
    await order.asave()
    
    try:
        msg = await callback.message.answer(
            text=capture,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Добавить фото/Скриншот', callback_data=f'admin_add_photo:{order.id}')],
                [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment_admin:{order.id}')],
                [InlineKeyboardButton(text='Отправить в цех', callback_data=f'admin_to_chat:{order.id}')],
            ])
        )
        
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
    except Exception as e:
        await callback.answer('Что-то не так с введеными данными о клиенте, попробуйте снова', show_alert=True)
        print(e)
        await state.clear()

    
@router.message(F.text, DateClient.wait_cost)
async def f(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=message.message_id
    )
    
    try:
        num = float(message.text)
    except Exception as e:
        msg = await message.answer('Введено некоректное значение, введите просто число')
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=msg.message_id
        )
        print(e)
        return  
        
    await state.update_data(cost=message.text)
    
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
    products_text = get_order_composition_text(order)
    products_text_full = await get_order_types_text(order)
    if order.order_type == 'measurement':
        capture = (
            f"#{order.get_order_type_display()}\n"
            f"Заказ №{order.id}\n"
            f"Адрес: {client.address}\n"
            f"Номер телефона: {client.phone_number}\n"
            f"ФИО: {client.name}\n"
            f"Стоимость замера: {data.get('cost')}\n\n" 
            f"{products_text}" 
        )

        order.measurement_cost = data.get('cost')
        await order.asave()
    else:
        capture = (
            f"#{order.get_order_type_display()}\n"
            f"Заказ №{order.id}\n"
            f"Адрес: {client.address}\n"
            f"Номер телефона: {client.phone_number}\n"
            f"ФИО: {client.name}\n"
            f"{products_text_full}" 
        )
    await state.update_data(capture=capture)
    
    order.current_caption = capture
    await order.asave()

    if order.order_type != 'measurement':
        try:
            mess = await message.answer(
                text=capture,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Добавить фото/Скриншот', callback_data=f'admin_add_photo:{order.id}')],
                    [InlineKeyboardButton(text='Внести замер как текст', callback_data=f'driver_add_text:{order.id}')],
                    [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment_admin:{order.id}')],
                    [InlineKeyboardButton(text='Отправить в цех', callback_data=f'admin_to_chat:{order.id}')],
                ])
            )
            await ActiveMessage.objects.acreate(
                order=order,
                chat_id=user.id,
                msg_id=mess.message_id
            )
        except Exception as e:
            m = await message.answer('Что-то не так с введеными данными о клиенте, попробуйте снова')
            await ActiveMessage.objects.acreate(
                order=order,
                chat_id=user.id,
                msg_id=m.message_id
            )
            await state.clear()
    else:
        try:
            await message.answer(
                text=capture,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Отправить на замер', callback_data=f'admin_to_chat_2:{order.id}')],
                    [InlineKeyboardButton(text='Добавить коментарий', callback_data=f'add_comment_admin:{order.id}')],
                ])
            )
        except Exception as e:
            await message.answer('Что-то не так с введеными данными о клиенте, попробуйте снова')
            await state.clear()


@router.callback_query(F.data.startswith('add_comment_admin:'))
async def chat1(callback: CallbackQuery, bot: Bot, state: FSMContext, user: User):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    await state.update_data(ord_id=order_id)
    msg = await callback.message.answer(text='Введите коментарий к заказу: ')
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    await state.set_state(DateClient.wait_comment)


@router.message(F.text, DateClient.wait_comment)
async def comm_f(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    order_id = data.get('ord_id')
    order = await Order.objects.aget(id=order_id)

    order.comments = message.text
    order.current_caption += f'\n\nКоментарий: {message.text}'
    await order.asave()

    msg = await message.answer('Комментарий добавлен')
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )
    await message.delete()


@router.callback_query(F.data.startswith('admin_to_chat_2:'))
async def chat1(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    capture = order.current_caption
    
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
    
    await delete_previous_order_messages_bd(bot=bot, order=order)
    
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

        products_text = await get_order_composition_text_for_workshop(order)
        caption = ''
        if order.comments is not None:
            caption = f"#{order.get_order_type_display()}\nЗаказ №{order.id}\nАдрес: {client.address}\nНомер телефона: {client.phone_number}.\nФИО: {client.name}\n\n{products_text}\n\nКоментарии: {order.comments}"
        else:
            caption = f"#{order.get_order_type_display()}\nЗаказ №{order.id}\nАдрес: {client.address}\nНомер телефона: {client.phone_number}.\nФИО: {client.name}\n\n{products_text}"

        media_group = MediaGroupBuilder(caption=caption)
        for photo_object in photos:
            media_group.add_photo(media=photo_object.file_id)
        
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
        
        await delete_previous_order_messages_bd(bot=bot, order=order)
        
        new_message_ids = [m.message_id for m in sent_media_messages]
        new_message_ids.append(sent_action_message.message_id)

        order.active_messages_info = {
            "chat_id": config.CHAT4_ID,
            "message_ids": new_message_ids,
        }
        
        chat = await bot.get_chat(chat_id=config.CHAT4_ID)
        chat_title = chat.title
        order.chat_location = chat_title
        order.status = 'sent_to_workshop'
        await callback.message.edit_text(f"Заказ №{order.id} успешно отправлен в цех.")
        await order.asave()
        await state.clear()
        
    except Exception as e:
        print(f"Произошла ошибка при отправке: {e}")
       
        
@router.callback_query(F.data.startswith('admin_add_photo:'))
async def photo_send(callback: CallbackQuery, state: FSMContext, user: User):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    await state.update_data(order_id_for_photo=order_id)
    
    msg = await callback.message.answer(
        text='Отправьте 1 или несколько фото: '
    )
    
    await ActiveMessage.objects.acreate(
        order=order,
        chat_id=user.id,
        msg_id=msg.message_id
    )

    await state.set_state(DateClient.wait_photo)
    await callback.answer('')
    
    
@router.message(DateClient.wait_photo)
async def album_and_photo_save_to_db(message: Message, user: User, state: FSMContext, album: list[Message] | None = None):
    data = await state.get_data()
    order_id = data.get('order_id_for_photo')
    order = await Order.objects.aget(id=order_id)

    if not order_id:
        await message.answer("Произошла ошибка, не могу определить для какого заказа это фото. Пожалуйста, начните заново, нажав 'Добавить фото' у нужного заказа.")
        await state.clear()
        return

    messages_to_process = album or [message]

    saved_photos_count = 0
    try:
        for msg in messages_to_process:
            await ActiveMessage.objects.acreate(
                order=order,
                chat_id=user.id,
                msg_id=msg.message_id
            )
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
        mes = await message.answer(f"Добавлено к заказу: {saved_photos_count} фото.")
        await ActiveMessage.objects.acreate(
            order=order,
            chat_id=user.id,
            msg_id=mes.message_id
        )
    