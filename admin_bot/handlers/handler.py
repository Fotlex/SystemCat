from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from panel.models import User, Order, Client, StartOrder
from admin_bot.keyboards import *
from admin_bot.states import DateClient
from config import config


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
            [InlineKeyboardButton(text='СТАТУСЫ', callback_data='start_order')],
            [InlineKeyboardButton(text='АНАЛИТИКА', callback_data='start_order')]
        ])
    )
    
    
@router.callback_query(F.data == 'start_order')
async def f(callback: CallbackQuery):
    await callback.message.edit_text(
        text='Какой тип заказа?',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='ЗАМЕР', callback_data='type_measurement')],
            [InlineKeyboardButton(text='ЗАКАЗ-НАРЯД', callback_data='type_delivery')],
            [InlineKeyboardButton(text='ДОСТАВКА', callback_data='type_workOrder')]
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
                [InlineKeyboardButton(text='ГОРОД', callback_data='measurement_city')],
                [InlineKeyboardButton(text='МЕЖГОРОД', callback_data='measurement_intercity')],
            ])
        )
        return
    
    
    await callback.message.edit_text(
        text='Начнем ввод данных клиента.\nВведите его имя',
        reply_markup=None
    )
    
    await state.set_state(DateClient.wait_name)
    

@router.callback_query(F.data.startswith('measurement_'))
async def f(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order = await Order.objects.aget(id=data.get('order_id'))
    
    order.subtype = callback.data.split('_')[1]
    await order.asave()
    
    await callback.message.edit_text(
        text='Начнем ввод данных клиента.\nВведите его имя',
        reply_markup=None
    )
    
    await state.set_state(DateClient.wait_name)
    

@router.message(F.text, DateClient.wait_name)
async def f(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(DateClient.wait_phone)
    
    await message.answer(text='Введите номер телефона клиента')
    
    
@router.message(F.text, DateClient.wait_phone)
async def f(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
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
    
    await state.clear()

    capture = ''
    
    if order.order_type == 'measurement' and order.subtype == 'city':
        capture = f'Заявка {order.id}: Замер, {client.name}, {client.phone_number}, {client.address}'
        await StartOrder.objects.acreate(
            order=order,
            capture=capture,
            chat_id=config.CHAT1_ID,
        )
        return
    
    if order.order_type == 'measurement' and order.subtype == 'intercity':
        id_emploey = await User.objects.aget(role='F')
        capture = f'Заявка {order.id}: Замер, {client.name}, {client.phone_number}, {client.address}'
        await StartOrder.objects.acreate(
            order=order,
            capture=capture,
            chat_id=id_emploey,
        )
        return   
    
    if order.order_type == 'workOrder':
        capture = f'Заявка {order.id}: Заказ-наряд, {client.name}, {client.phone_number}, {client.address}'
        await StartOrder.objects.acreate(
            order=order,
            capture=capture,
            chat_id=config.CHAT2_ID,
        )
        return   
        
    if order.order_type == 'delivery':
        capture = f'Заявка {order.id}: Доставка, {client.name}, {client.phone_number}, {client.address}'
        await StartOrder.objects.acreate(
            order=order,
            capture=capture,
            chat_id=config.CHAT2_ID,
        )
        return   
        