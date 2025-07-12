from aiogram.fsm.state import StatesGroup, State


class DateClient(StatesGroup):
    wait_name = State()
    wait_phone = State()
    wait_address = State()