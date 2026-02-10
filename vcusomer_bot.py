# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import threading
from flask import Flask

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardRemove
)

# --- НАСТРОЙКИ ---
TOKEN = "8585043014:AAENR0EdGSFGxOOZwbCGVjibJBEkMVa9VR4"
TELEGRAM_CHANNEL_URL = "https://t.me/+YOEpXfsmd9tiODQ6"

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ БЛОКОВ И РЕЦЕПТОВ ---
# Мы структурируем ваши данные так, чтобы бот мгновенно находил нужный блок
MENU_DATA = {
    "Похудеть": {
        "Сидячий образ жизни": "А",
        "Средняя активность": "Б",
        "Высокая активность": "В"
    },
    "Поддерживать вес": {
        "Сидячий образ жизни": "Г",
        "Средняя активность": "Д",
        "Высокая активность": "Е"
    },
    "Набрать массу": {
        "Сидячий образ жизни": "Ж",
        "Средняя активность": "З",
        "Высокая активность": "И"
    }
}

# Тексты блюд по блокам и аллергиям
BLOCKS_CONTENT = {
    "А": {
        "none": "Завтрак: Омлет (2 яйца) + тост.\nОбед: Куриное филе (120г) + гречка (40г) + огурец.\nУжин: Треска (150г) + брокколи.",
        "gluten": "Завтрак: Омлет + рисовый хлебец.\nОбед: Курица + киноа (40г) + огурец.\nУжин: Треска + брокколи.",
        "lactose": "Завтрак: Омлет (на оливковом масле) + тост.\nОбед: Курица + гречка + огурец.\nУжин: Треска + овощной салат (без сметаны).",
        "seafood": "Завтрак: Омлет + тост.\nОбед: Куриное филе + гречка.\nУжин: Индейка (150г) вместо рыбы + брокколи.",
        "nuts": "Завтрак: Омлет + тост.\nОбед: Куриное филе + гречка.\nУжин: Треска + брокколи. (Без соусов и посыпок!)"
    },
    # Для краткости примера я добавлю логику выбора, остальные блоки Б-И заполняются аналогично
}

# Рецепты
RECIPES_TEXT = {
    "breakfast_1": "🍳 Рецепт №1: Базовый Омелет\n- Взбей 2 яйца + 20мл воды/молока.\n- Жарь под крышкой 4 мин.\n- Модификация: Если Глютен-фри - бери рисовый хлебец. Если без лактозы - жарь на оливковом масле.",
    "lunch_3": "🍗 Рецепт №3: Курица/Индейка со злаками\n- Мясо режь кубиками, жарь 8 мин.\n- Крупу залей кипятком (1:2) на 15 мин.\n- Без глютена: бери только гречку или рис.",
    "dinner_5": "🐟 Рецепт №5: Рыба в кармашке\n- Рыбу и брокколи заверни в фольгу.\n- Сбрызни лимоном.\n- Запекай 15 мин в духовке (180С) или 6 мин в микроволновке."
}

# --- СОСТОЯНИЯ ---
class Survey(StatesGroup):
    gender = State()
    goal = State()
    activity = State()
    age = State()
    height = State()
    weight = State()
    allergies = State()
    viewing_menu = State()

# --- КЛАВИАТУРЫ ---
start_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Погнали! 🚀")]], resize_keyboard=True)
gender_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
goal_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Поддерживать вес"), KeyboardButton(text="Набрать массу")]], resize_keyboard=True)
activity_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий образ жизни"), KeyboardButton(text="Средняя активность"), KeyboardButton(text="Высокая активность")]], resize_keyboard=True)

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Я — Вкусомер 🥗. Давай составим твой план на 7 дней!", reply_markup=start_kb)

@dp.message(F.text == "Погнали! 🚀")
async def start_survey(message: types.Message, state: FSMContext):
    await message.answer("Выбери свой пол:", reply_markup=gender_kb)
    await state.set_state(Survey.gender)

@dp.message(Survey.gender)
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.
    answer("Какая у тебя цель?", reply_markup=goal_kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal)
async def process_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await message.answer("Уровень активности?", reply_markup=activity_kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity)
async def process_activity(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("Введи возраст, рост и вес через пробел (например: 25 180 75):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def process_stats(message: types.Message, state: FSMContext):
    # Упрощенный ввод для скорости
    await message.answer(
        "Есть ли аллергии? Отметь или нажми 'Результат'.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Лактоза", callback_data="all_lactose")],
            [InlineKeyboardButton(text="❌ Глютен", callback_data="all_gluten")],
            [InlineKeyboardButton(text="✅ Я всё ем / Готово", callback_data="calculate")]
        ])
    )
    await state.update_data(allergies=[])
    await state.set_state(Survey.allergies)

@dp.callback_query(F.data.startswith("all_"))
async def add_allergy(callback: types.CallbackQuery, state: FSMContext):
    allergy = callback.data.split("_")[1]
    data = await state.get_data()
    data['allergies'].append(allergy)
    await state.update_data(allergies=data['allergies'])
    await callback.answer(f"Добавлено: {allergy}")

@dp.callback_query(F.data == "calculate")
async def show_result(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Определяем блок
    block = MENU_DATA.get(data['goal'], {}).get(data['activity'], "А")
    await state.update_data(current_block=block)
    
    await callback.message.answer(
        f"✅ План готов! Твой блок: {block}.\nМы подготовили меню на 7 дней.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="День 1", callback_data="day_1"), InlineKeyboardButton(text="День 2", callback_data="day_2")],
            [InlineKeyboardButton(text="День 3", callback_data="day_3"), InlineKeyboardButton(text="День 4", callback_data="day_4")],
            [InlineKeyboardButton(text="День 5", callback_data="day_5"), InlineKeyboardButton(text="День 6", callback_data="day_6")],
            [InlineKeyboardButton(text="День 7", callback_data="day_7")]
        ])
    )

@dp.callback_query(F.data.startswith("day_"))
async def show_day_menu(callback: types.CallbackQuery, state: FSMContext):
    day = callback.data.split("_")[1]
    data = await state.get_data()
    block = data['current_block']
    
    # Логика выбора аллергии (берем первую или 'none')
    allergy_key = data['allergies'][0] if data['allergies'] else "none"
    
    # Получаем текст меню (в реальности тут будет словарь для каждого дня)
    menu_text = BLOCKS_CONTENT.get(block, BLOCKS_CONTENT["А"]).get(allergy_key, "Завтрак, Обед, Ужин")
    
    await callback.message.answer(
        f"📅 **ДЕНЬ {day}**\n\n{menu_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨‍🍳 Как готовить?", callback_data="show_recipes")]
        ])
    )

@dp.callback_query(F.data == "show_recipes")
async def show_recipes(callback: types.CallbackQuery):
    # Выводим рецепты
    text = f"{RECIPES_TEXT['breakfast_1']}\n\n{RECIPES_TEXT['lunch_3']}\n\n{RECIPES_TEXT['dinner_5']}"
    await callback.message.answer(text)
    await asyncio.sleep(2)
    await callback.message.answer("Чтобы получить список продуктов на неделю и доступ к чату - оформи подписку!", 
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                      [InlineKeyboardButton(text="Подписка 290₽", callback_data="sub")]
                                  ]))

# --- ЗАПУСК ---
@app.route('/')
def index(): return "Alive"

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(dp.start_polling(bot))

threading.Thread(target=run_bot, daemon=True).start()

if name == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
