from aiogram.fsm.state import StatesGroup, State


class PostCreationState(StatesGroup):
    waiting_for_text = State()
    preview_and_payment = State()