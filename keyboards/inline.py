from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_invoice_keyboard(stars_price: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для сообщения с инвойсом.
    По правилам Telegram Bot API, первой кнопкой обязательно должна быть кнопка с pay=True.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Оплатить {stars_price} ⭐️",
                    pay=True,
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_invoice",
                )
            ],
        ]
    )