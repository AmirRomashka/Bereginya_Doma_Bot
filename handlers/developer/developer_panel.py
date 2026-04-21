import os
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from sqlalchemy.ext.asyncio import AsyncSession

from keybords.inline import get_callback_btns
from config import last_message_dict
from tools import message_delete

DeveloperPanelRouter = Router()

@DeveloperPanelRouter.message(Command("developer"), lambda message: message.from_user.id == os.getenv("developer_id"))
async def dev_panel(message : types.Message, state : FSMContext, session : AsyncSession):

    dev_meet_text = "Hello Amir Gafarov"

    dev_buttons = {
        "soon" : "soon"
    }

    msg = await message.answer(text = dev_meet_text, reply_markup = get_callback_btns(btns = dev_buttons))

    await message_delete(user_id = message.from_user.id, last_message = last_message_dict)
    last_message_dict[message.from_user.id].extend([msg.message_id])

