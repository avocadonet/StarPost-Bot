import logging
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PreCheckoutQuery, MessageEntity

from config import config
from db import is_duplicate_charge, log_transaction

logger = logging.getLogger(__name__)
router = Router(name="payments_router")


def build_post_link(chat_id: int, username: str | None, message_id: int) -> str | None:
    """Формирует прямую ссылку на опубликованное сообщение в публичной или приватной супергруппе."""
    if username:
        return f"https://t.me/{username}/{message_id}"
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        internal_id = chat_id_str[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"
    return None


@router.pre_checkout_query()
async def handle_pre_checkout(
    pre_checkout_query: PreCheckoutQuery,
    state: FSMContext,
    bot: Bot,
) -> None:
    """
    Валидация перед списанием звезд (тайм-аут ответа — до 10 секунд).
    Проверяем актуальность заказа в FSM и доступность целевой группы.
    """
    data = await state.get_data()
    expected_payload = data.get("order_payload")
    order_text = data.get("order_text")

    if not expected_payload or pre_checkout_query.invoice_payload != expected_payload or not order_text:
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=pre_checkout_query.id,
            ok=False,
            error_message="Сессия заказа устарела или была отменена. Создайте новый пост через /start.",
        )
        return

    # Быстрая проверка, что бот не удален из целевой группы до списания средств
    try:
        await bot.get_chat(config.target_group_id)
    except Exception as e:
        logger.error("Target group check failed during pre_checkout: %s", e)
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=pre_checkout_query.id,
            ok=False,
            error_message="Целевая группа временно недоступна. Попробуйте позже.",
        )
        return

    await bot.answer_pre_checkout_query(
        pre_checkout_query_id=pre_checkout_query.id,
        ok=True,
    )


@router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message,
    state: FSMContext,
    bot: Bot,
) -> None:
    payment = message.successful_payment
    charge_id = payment.telegram_payment_charge_id
    payload = payment.invoice_payload
    user_id = message.from_user.id
    amount = payment.total_amount

    # Защита от дублирования транзакций
    if await is_duplicate_charge(charge_id):
        logger.warning("Duplicate payment event ignored: %s", charge_id)
        return

    await log_transaction(
        charge_id=charge_id,
        payload=payload,
        user_id=user_id,
        amount=amount,
        status="paid",
    )

    data = await state.get_data()
    order_text: str | None = data.get("order_text")
    raw_entities: list[dict] = data.get("order_entities", [])
    order_entities = [MessageEntity(**e) for e in raw_entities] if raw_entities else None

    # Сразу очищаем FSM, чтобы пользователь не застрял в состоянии оплаты
    await state.clear()

    # Если бот перезапускался с MemoryStorage ровно в секунду между pre_checkout и successful_payment
    if not order_text:
        await _refund_and_notify(
            bot=bot,
            message=message,
            charge_id=charge_id,
            payload=payload,
            amount=amount,
            error_reason="Потеря контекста сообщения (перезапуск состояния FSM).",
        )
        return

    # Публикация в целевую группу
    try:
        sent_msg = await bot.send_message(
            chat_id=config.target_group_id,
            text=order_text,
            entities=order_entities,
            parse_mode=None,
        )
        await log_transaction(
            charge_id=charge_id,
            payload=payload,
            user_id=user_id,
            amount=amount,
            status="published",
        )

        post_link = build_post_link(
            chat_id=sent_msg.chat.id,
            username=sent_msg.chat.username,
            message_id=sent_msg.message_id,
        )
        link_block = (
            f"\n🔗 <a href='{post_link}'>Перейти к опубликованному сообщению</a>"
            if post_link
            else ""
        )

        await message.answer(
            f"✅ <b>Оплата прошла успешно! Ваше объявление опубликовано.</b>{link_block}\n\n"
            "Чтобы разместить еще одно сообщение, нажмите /start.",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    except Exception as exc:
        logger.exception("Failed to publish paid post to group %s: %s", config.target_group_id, exc)
        await _refund_and_notify(
            bot=bot,
            message=message,
            charge_id=charge_id,
            payload=payload,
            amount=amount,
            error_reason=f"{type(exc).__name__}: {exc}",
        )


async def _refund_and_notify(
    bot: Bot,
    message: Message,
    charge_id: str,
    payload: str,
    amount: int,
    error_reason: str,
) -> None:
    """Выполняет автоматический возврат Telegram Stars и отправляет алерт администратору."""
    user_id = message.from_user.id
    refund_ok = False

    try:
        await bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id,
        )
        refund_ok = True
        await log_transaction(
            charge_id=charge_id,
            payload=payload,
            user_id=user_id,
            amount=amount,
            status="refunded",
        )
        await message.answer(
            "⚠️ Произошла техническая ошибка при публикации в группу.\n"
            "💫 <b>Ваши звезды автоматически возвращены на ваш баланс!</b>",
            parse_mode="HTML",
        )
    except Exception as refund_exc:
        logger.critical(
            "CRITICAL: Refund failed for user %s, charge_id %s: %s",
            user_id,
            charge_id,
            refund_exc,
        )
        await message.answer(
            "⚠️ Ошибка публикации. Автоматический возврат не удался — администратор уже уведомлен "
            f"и вернет средства вручную.\nID транзакции: <code>{charge_id}</code>",
            parse_mode="HTML",
        )

    # Алерт администратору платформы
    try:
        refund_status_text = "✅ Выполнен автоматически" if refund_ok else "❌ ОШИБКА ВОЗВРАТА (требуется ручной возврат)"
        await bot.send_message(
            chat_id=config.admin_id,
            text=(
                "🚨 <b>Алерт: сбой публикации оплаченного поста</b>\n\n"
                f"👤 <b>Пользователь:</b> <code>{user_id}</code> (@{message.from_user.username or 'нет'})\n"
                f"💳 <b>Charge ID:</b> <code>{charge_id}</code>\n"
                f"💰 <b>Сумма:</b> {amount} XTR\n"
                f"🔄 <b>Статус рефанда:</b> {refund_status_text}\n"
                f"❗️ <b>Причина сбоя:</b> <code>{error_reason}</code>"
            ),
            parse_mode="HTML",
        )
    except Exception as admin_exc:
        logger.error("Failed to send alert to admin %s: %s", config.admin_id, admin_exc)