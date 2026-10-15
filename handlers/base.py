from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import config
from states import PostCreationState

router = Router(name="base_router")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    # Если у пользователя остался неоплаченный инвойс, пробуем удалить его
    data = await state.get_data()
    if invoice_msg_id := data.get("invoice_message_id"):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=invoice_msg_id)
        except TelegramBadRequest:
            pass

    await state.clear()
    await state.set_state(PostCreationState.waiting_for_text)

    await message.answer(
        "👋 <b>Добро пожаловать в сервис платных публикаций!</b>\n\n"
        "📋 <b>Правила размещения:</b>\n"
        "• Принимается только обычный текст (без фото, видео и прочих медиафайлов).\n"
        "• Поддерживается стандартное форматирование Telegram (жирный, курсив, ссылки, спойлеры).\n"
        "• Максимальная длина текста — 4096 символов.\n"
        f"• Стоимость размещения: <b>{config.stars_price} ⭐️ (Telegram Stars)</b>.\n\n"
        "✍️ <b>Отправьте текст вашего объявления ответным сообщением:</b>",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Справка по работе с ботом:</b>\n\n"
        "/start — Начать создание новой публикации\n"
        "/cancel — Отменить текущий заказ и сбросить диалог\n\n"
        "После оплаты звездами ваш пост мгновенно публикуется в группе. "
        "Если по техническим причинам публикация не удастся, звезды вернутся на ваш баланс автоматически.",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, bot: Bot) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активного процесса создания публикации. Нажмите /start, чтобы начать.")
        return

    data = await state.get_data()
    if invoice_msg_id := data.get("invoice_message_id"):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=invoice_msg_id)
        except TelegramBadRequest:
            pass

    await state.clear()
    await message.answer(
        "❌ Создание публикации отменено. Чтобы отправить новое объявление, нажмите /start."
    )


@router.callback_query(F.data == "cancel_invoice")
async def cb_cancel_invoice(callback: CallbackQuery, state: FSMContext) -> None:
    """По графу состояний 3.1 кнопка 'Отмена' возвращает пользователя в WAITING_FOR_TEXT."""
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await state.set_state(PostCreationState.waiting_for_text)
    await state.set_data({})

    await callback.message.answer(
        "🔄 Инвойс отменен.\n\n"
        "Вы можете отправить исправленный текст объявления прямо сейчас или нажать /cancel для полного выхода."
    )
    await callback.answer()