from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder

from panel.models import User, Order, Client, OrderPhoto 
from admin_bot.keyboards import *
from admin_bot.states import WorkStates
from config import config


router = Router()


@router.callback_query(F.data.startswith('cancel:'))
async def cans(callback: CallbackQuery):
    order_id = int(callback.data.split(':')[1])
    order = await Order.objects.aget(id=order_id)
    
    pass


@router.callback_query(F.data.startswith('take_zamer:'))
async def cans(callback: CallbackQuery, user: User, bot: Bot):
    order_id = int(callback.data.split(':')[1])

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

    await callback.message.delete()

    
@router.callback_query(F.data.startswith('driver_to_men:'))
async def send_order_to_workshop(callback: CallbackQuery, bot: Bot, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    data = await state.get_data()
    
    try:
        current_order = await Order.objects.aget(id=order_id)
        order = await Order.objects.select_related('client').aget(id=order_id)
        client = order.client
        photos = [p async for p in order.photos.all()]

        if not photos:
            await callback.answer(
                "К заказу не приложены фотографии. Пожалуйста, сначала добавьте их.",
                show_alert=True
            )
            return

        caption = callback.message.text
        current_order.current_caption = caption

        media_group = MediaGroupBuilder(caption=caption)
        for photo_object in photos:
            media_group.add_photo(media=photo_object.file_id)
        
        await bot.send_media_group(
            chat_id=config.CHAT3_ID,
            media=media_group.build(),
        )
        await bot.send_message(
            chat_id=config.CHAT3_ID,
            text=f"Действия для заказа №{order_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Отправить в цех', callback_data=f'send_work_place:{order_id}')],
                [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
            ])
        )
        await callback.message.delete()
        chat = await bot.get_chat(chat_id=config.CHAT3_ID)
        chat_title = chat.title
        current_order.chat_location = chat_title
        await current_order.asave()
        await order.asave()
        await state.clear()
        
    except Exception as e:
        print(f"Произошла ошибка при отправке: {e}")
        await callback.message('Произошла ошибка, попробуйте создать заказ снова')


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
        await bot.send_media_group(
            chat_id=config.CHAT4_ID,
            media=media_group.build(),
        )
        await bot.send_message(
            chat_id=config.CHAT4_ID,
            text=f"Действия для заказа №{order_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='В работу', callback_data=f'in_work:{order_id}')],
                [InlineKeyboardButton(text='Отмена', callback_data=f'cancel:{order_id}')],
            ])
        )
        await state.clear()
        return
    
    await state.update_data(order_id=order_id)
    await callback.message.answer('Введите стоимость изделия: ')
    await state.set_state(WorkStates.wait_cost)


@router.message(F.text, WorkStates.wait_cost)
async def set_cost(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    order = await Order.objects.aget(id=order_id)


    try:
        order.product_cost = float(message.text)
        order.current_caption += f'\nСтоимость изделия: {order.product_cost}'

        await order.asave()
    except Exception as e:
        print(e)
        await message.answer('Вы ввели некоректное число, введите число еще раз')


@router.callback_query(F.data.startswith('driver_add_photo:'))
async def photo_add(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(':')[1])
    await state.update_data(order_id_for_photo=order_id)
    await callback.message.answer('Отправьте 1 или несколько фото замеров, размеры замеров тоже лучше отправлять в виде фото/скриншота')

    await state.set_state(WorkStates.wait_photo)


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


@router.message(F.text, WorkStates.wait_text_size)
async def mess(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    order = await Order.objects.aget(id=order_id)

    try:
        order.current_caption += f'Добавленный замер: \n{message.text}'
        await order.asave()

        await message.answer('Текст замера успешно добавлен')
    except Exception as e:
        print(e)
