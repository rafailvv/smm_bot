from aiogram import Router
from aiogram.types import CallbackQuery

import asyncio
import os
import uuid

import PIL.ImageOps
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    PreCheckoutQuery,
    InputFile,
    FSInputFile,
    CallbackQuery,
    InputMediaPhoto,
    InputMediaDocument
)
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject

from dotenv import dotenv_values
import pandas as pd
import Database.database as db
from Bot.misc.states import SmmStatesGroup as st
from Bot.misc.methods import *
from PIL import Image, ImageDraw

from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from aiogram.fsm.storage.redis import RedisStorage, Redis

from datetime import datetime, timedelta


async def pay_for_publication(user_id, duration, price):
    buttons = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Оплатить", pay=True)]]
    )
    await bot.send_invoice(
        chat_id=user_id,
        title="Опубликовать свой профиль",
        description="После публикации ваш профиль смогут найти заинтересованные пользователи",
        provider_token=config["PAY_TOKEN"],
        currency="RUB",
        # photo_url="https://i.ibb.co/448wWGc/avatar.png",
        # photo_width=640,
        # photo_height=640,
        # is_flexible=False,
        prices=[LabeledPrice(label="Цена", amount=price * 100)],
        start_parameter="time-machine-example",
        payload=f"post|{duration}",
        # need_email=True,
        # send_email_to_provider=True,
        # provider_data={
        #     "receipt": {
        #         "items": [
        #             {
        #                 "description": "билет на ",
        #                 "quantity": "1.00",
        #                 "amount": {
        #                     "value": str(price),
        #                     "currency": "RUB",
        #                 },
        #                 "vat_code": 2,
        #             }
        #         ]
        #     }
        # },
        reply_markup=buttons,
    )


async def contacts(message: Message, state: FSMContext, dict_of_smm, i=0, fl=True):
    if len(dict_of_smm) == 0:
        await message.answer("🤷‍♂️ Вы пока ещё не выбрали ни одного контакта")
    smm = dict_of_smm[i]
    user_id = smm[0]
    user_info = smm[1]
    smm_id, name, phone, user_id, age, city, cost, photo, tg, description = user_info[0].split(",")
    prev = InlineKeyboardButton(
        text="⬅️ Предыдущий", callback_data=f"contacts_smm|prev"
    )
    next = InlineKeyboardButton(text="Следующий ➡️", callback_data=f"contacts_smm|next")
    await state.update_data(dos=dict_of_smm)
    await state.update_data(it=i)
    btns = []
    if len(dict_of_smm) > 1:
        if i == 0:
            btns = [[next]]
        elif i == len(dict_of_smm) - 1:
            btns = [[prev]]
        else:
            btns = [[prev, next]]
    btns = InlineKeyboardMarkup(inline_keyboard=btns)
    photo = FSInputFile(os.path.join(f"API/profile/templates/images/{user_id}.jpg"))
    if not fl:

        await message.answer_photo(
            photo,
            caption=f"""🙌 Имя: {name[1:-1]}\n📞 Номер телефона: {phone}\n🎂 Возраст: {age}\n🏙 Город: {city}\n💬 Телеграм: @{tg}\n📝 Описание: {description[:-1]}\n💸 Цена за месяц: от {cost} руб.""",
            reply_markup=btns,
        )
    else:
        await message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=f"""🙌 Имя: {name[1:-1]}\n📞 Номер телефона: {phone}\n🎂 Возраст: {age}\n🏙 Город: {city}\n💬 Телеграм: @{tg}\n📝 Описание: {description[:-1]}\n💸 Цена за месяц: от {cost} руб.""",
            ),
            reply_markup=btns,
        )


async def ta_choose(message: Message, t=None, fl=True):
    if t is None:
        t = []
        target_audience = await db.get_all_field()
        for i in range(len(target_audience)):
            t.append(target_audience[i][0])
    btns = []
    for i in range(len(t)):
        btns.append([InlineKeyboardButton(text=f"{t[i]}", callback_data=f"ta|{i}")])
    btns.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="ta|back"),
                 InlineKeyboardButton(text="Принять", callback_data="ta|done")])

    btns = InlineKeyboardMarkup(inline_keyboard=btns)
    if fl:
        await message.edit_text(
            text="Выбери вашу сферу(ы) деятельности👇", reply_markup=btns
        )
    else:
        await message.edit_reply_markup(reply_markup=btns)


async def send_notification(message: Message):
    user_id = message.chat.id
    tas = await db.get_ta_by_user_id(user_id)
    smm_id, full_name, phone, user_id, age, town, cost, photo, username, description, date_sub = await db.get_profile_by_id(
        user_id)
    if None in [full_name, phone, age, town, cost, description, date_sub] or len(tas) == 0 or f"{user_id}.jpg" not in os.listdir("profile/templates/images"):
        btn = [[KeyboardButton(text="Меню ☰")], [KeyboardButton(text="Избранные контакты 🤝")],
               [KeyboardButton(text="Оформить подписку 🎟")]]
        btn = ReplyKeyboardMarkup(keyboard=btn, resize_keyboard=True)
        await message.answer(text=f"{message.chat.first_name}, у вас не заполнен профиль,\nвы можете дозаполнить, чтобы опубликовать его, нажав на кнопку 'Профиль'", reply_markup=btn)


async def cut_photo(user_id, file_path):
    photo = Image.open(f"API/profile/templates/images/{user_id}.{file_path.split('.')[-1]}")
    try:
        os.remove(f"API/profile/templates/images/{user_id}.{file_path.split('.')[-1]}")
    except:
        pass
    width, height = photo.size
    pix = photo.load()
    if height > width:
        photo = photo.crop((0, (height - width) // 2, width, width + (height - width) // 2))
    else:
        photo = photo.crop(((width - height) // 2, 0, height + (width - height) // 2, height))

    photo = photo.convert("RGB")

    photo.save(f"API/profile/templates/images/{user_id}.{file_path.split('.')[-1]}")


async def change_photo(message: Message, state: FSMContext):
    await message.answer(text="Пришлите фотографию вашего профиля 📸")
    await state.set_state(st.photo)


async def send_description(message: Message, state: FSMContext):
    await message.answer("Опишите ваши услуги в текстовом сообщении")
    await state.set_state(st.description)


async def search_by_ta(message: Message, t=None, fl=True):
    if t is None:
        t = []
        target_audience = await db.get_all_field()
        for i in range(len(target_audience)):
            t.append(target_audience[i][0])
        # t.append("Применить")

    btns = []
    for i in range(len(t)):  # - 1
        btns.append([InlineKeyboardButton(text=f"{t[i]}", callback_data=f"talook|{i}")])
    btns.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="talook|back"),
                 InlineKeyboardButton(text="Применить", callback_data="talook|done")])
    btns = InlineKeyboardMarkup(inline_keyboard=btns)
    if fl:
        await message.edit_text(
            text="Выберите вашу категорию(и) сферы деятельности👇", reply_markup=btns
        )
    else:
        await message.edit_reply_markup(reply_markup=btns)


async def search_by_town(message: Message, state: FSMContext, dict_of_smm):
    await message.answer(text='Введите город, если неважно введите "-" (без кавычек)')
    await state.update_data(town=True)
    await state.update_data(town_d=dict_of_smm)


async def search_by_cost(message: Message, state: FSMContext, dict_of_smm):
    await message.answer(text="Введите начальную цену услуг")
    await state.update_data(cost=True)
    await state.update_data(cost_d=dict_of_smm)


async def list_of_smm(message: Message, dict_of_smm, i, state: FSMContext, fl=False):
    n = len(dict_of_smm)
    if n == 0:
        await message.answer(text="🥲 К сожалению, не найдено ни одного специалиста")
    else:
        smm = dict_of_smm[i]
        user_id = smm[0]
        user_info = smm[1]
        buy = InlineKeyboardButton(
            text="Добавить в избранное 💰", callback_data=f"choose_smm|buy|{user_id}"
        )
        prev = InlineKeyboardButton(
            text="⬅️ Предыдущий", callback_data=f"choose_smm|prev"
        )
        next = InlineKeyboardButton(
            text="Следующий ➡️", callback_data=f"choose_smm|next"
        )
        await state.update_data(dos=dict_of_smm)
        await state.update_data(it=i)
        if n == 1:
            btns = [[buy]]
        elif i == 0:
            btns = [[buy], [next]]
        elif i == len(dict_of_smm) - 1:
            btns = [[buy], [prev]]
        else:
            btns = [[buy], [prev, next]]
        btns = InlineKeyboardMarkup(inline_keyboard=btns)
        photo = FSInputFile(os.path.join(f"API/profile/templates/images/{user_id}.jpg"))
        if not fl:
            await message.answer_photo(
                photo=photo,
                caption=f"""🙌 Имя: {user_info[0]}\n📞 Номер телефона: {(await db.get_phone_by_user_id(user_id))[0]}\n🎂Возраст: {user_info[1]}\n🏙 Город: {user_info[2]}\n💬 Телеграм: @{(await db.get_tg_by_user_id(user_id))[0]}\n💸 Цена за месяц: от {user_info[4]} руб.\n📝 Описание: {user_info[6]}""",
                reply_markup=btns,
            )
        else:
            await message.edit_media(
                media=InputMediaPhoto(
                    media=photo,
                    caption=f"""🙌 Имя: {user_info[0]}\n📞 Номер телефона: {(await db.get_phone_by_user_id(user_id))[0]}\n🎂Возраст: {user_info[1]}\n🏙 Город: {user_info[2]}\n💬 Телеграм: @{(await db.get_tg_by_user_id(user_id))[0]}\n💸 Цена за месяц: от {user_info[4]} руб.\n📝 Описание: {user_info[6]}""",
                ),
                reply_markup=btns,
            )
        if n == 1 and not fl:
            await message.answer(text="🚀 Найден 1 специалист")
        elif n > 0 and not fl:
            if n % 10 == 1 and n % 100 != 11:
                await message.answer(text=f"🚀 Найдено {n} специалист")
            elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
                await message.answer(text=f"🚀 Найдено {n} специалиста")
            else:
                await message.answer(text=f"🚀 Найдено {n} специалистов")
        elif not fl:
            await message.answer(
                text=f"🚀 Найдено {n} специалист{'а' if n % 10 == 1 and n % 100 != 11 else 'ов'}"
            )


async def sub_end(message: Message):
    btns = [[InlineKeyboardButton(text="Продлить", callback_data="add_field|post")],
            [InlineKeyboardButton(text="Позже", callback_data="add_field|then")]]
    await message.answer(text="Ваша анкета больше не видна пользователям,\nХотите продлить подписку?")