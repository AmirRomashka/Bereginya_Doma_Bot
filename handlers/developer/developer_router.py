# handlers/user/user_router.py
from aiogram import Router

from handlers.developer.developer_panel import DeveloperPanelRouter



DeveloperRouter = Router()

# Подключаем все роутеры пользователя
DeveloperRouter.include_routers(
    DeveloperPanelRouter,
)