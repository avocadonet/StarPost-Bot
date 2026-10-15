from aiogram import Router

from .base import router as base_router
from .payments import router as payments_router
from .post_submission import router as post_submission_router


def setup_routers() -> Router:
    main_router = Router()
    # Порядок важен: сначала команды и платежи, затем фильтрация контента по состояниям
    main_router.include_router(base_router)
    main_router.include_router(payments_router)
    main_router.include_router(post_submission_router)
    return main_router