from aiogram.fsm.state import StatesGroup, State


class DateClient(StatesGroup):
    wait_name = State()
    wait_phone = State()
    wait_address = State()
    wait_photo = State()
    wait_cost = State()
    wait_type = State()
    dead_state = State()
    wait_comment = State()

    wait_reason_cancel = State()


class WorkStates(StatesGroup):
    wait_photo = State()
    wait_cost = State()
    wait_text_size = State()
    end_driver = State()
    wait_cansel_reason = State()
    wait_comment = State()