import uuid
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, LabeledPrice

from config import config
from keyboards import get_invoice_keyboard
from states import PostCreationState

router = Router(name="post_submission_router")

MAX_TEXT_LENGTH = 4096


@router.message(PostCreationState.waiting_for_text, F.text)
async def handle_valid_text(message: Message, state: FSMContext) -> None:
    text_length = len(message.text)
    if text_length > MAX_TEXT_LENGTH:
        await message.answer(
            f"⚠️ Ваше сообщение слишком длинное ({text_length} символов).\n"
            f"Максимально допустимая длина — {MAX_TEXT_LENGTH} символов. "
            f"Пожалуйста, сократите текст на {text_length - MAX_TEXT_LENGTH} симв. и отправьте его снова."
        )
        return

    # Сериализуем entities в словари для совместимости с любым FSM-хранилищем (Memory / Redis)
    raw_entities = (
        [entity.model_dump() for entity in message.entities]
        if message.entities
        else []
    )
    order_payload = f"order_{message.from_user.id}_{uuid.uuid4().hex[:12]}"

    # 1. Отправляем превью с сохранением исходного форматирования пользователя
    await message.answer("👁 <b>Превью вашего сообщения:</b>", parse_mode="HTML")
    await message.answer(
        text=message.text,
        entities=message.entities,
        parse_mode=None,
        disable_web_page_preview=True,
    )

    # 2. Выставляем нативный инвойс в Telegram Stars (XTR)
    invoice_msg = await message.answer_invoice(
        title="Публикация объявления",
        description="Автоматическое размещение вашего текстового сообщения в целевой группе.",
        payload=order_payload,
        currency="XTR",
        prices=[
            LabeledPrice(label="Публикация текста", amount=config.stars_price)
        ],
        provider_token="",  # Для Telegram Stars (XTR) всегда пустая строка
        reply_markup=get_invoice_keyboard(config.stars_price),
    )

    # 3. Сохраняем данные заказа и переводим FSM в состояние PREVIEW_AND_PAYMENT
    await state.update_data(
        order_text=message.text,
        order_entities=raw_entities,
        order_payload=order_payload,
        invoice_message_id=invoice_msg.message_id,
    )
    await state.set_state(PostCreationState.preview_and_payment)


@router.message(PostCreationState.waiting_for_text)
async def handle_non_text_in_waiting(message: Message) -> None:
    """Отклоняет любые нетекстовые сообщения (фото, видео, стикеры, голосовые и т.д.)."""
    await message.answer(
        "⚠️ Для публикации принимается только обычный текст без медиафайлов. "
        "Пожалуйста, отправьте текстовое сообщение."
    )


@router.message(PostCreationState.preview_and_payment)
async def handle_messages_during_payment(message: Message) -> None:
    """Подсказка пользователю, если он пытается прислать новый текст поверх открытого инвойса."""
    await message.answer(
        "⏳ У вас уже сформирован счет на оплату выше.\n"
        "Оплатите его или нажмите кнопку <b>«❌ Отменить»</b> под счетом, чтобы отправить другой текст.",
        parse_mode="HTML",
    )