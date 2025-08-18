from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           ReplyKeyboardMarkup, KeyboardButton)



window_type_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='ПВХ')],
    [KeyboardButton(text='Фасад')],
    [KeyboardButton(text='Деревянные')],
    [KeyboardButton(text='Раздвижные')],
], 
    resize_keyboard=True,
    one_time_keyboard=True
)


window_style_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Решетка на замках')],
    [KeyboardButton(text='Решетка на шпингалете')],
    [KeyboardButton(text='Вольер')],
    [KeyboardButton(text='Ограничитель')],
    [KeyboardButton(text='Дверь')],
    [KeyboardButton(text='Нестандарт(На барашках)')],
    [KeyboardButton(text='Полка для вольера')],
], 
    resize_keyboard=True,
    one_time_keyboard=True
)