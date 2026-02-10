# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import threading
import json
import random
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
TOKEN = os.environ.get('TOKEN', "8585043014:AAENR0EdGSFGxOOZwbCGVjibJBEkMVa9VR4")
TELEGRAM_CHANNEL_URL = "https://t.me/+YOEpXfsmd9tiODQ6"

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА РЕЦЕПТОВ ---
ALL_RECIPES = []
def load_recipes():
    global ALL_RECIPES
    try:
        if os.path.exists('recipes.json'):
            with open('recipes.json', 'r', encoding='utf-8') as f:
                ALL_RECIPES = json.load(f)
            logging.info(f"Успешно загружено {len(ALL_RECIPES)} рецептов.")
        else:
            logging.error("Критическая ошибка: Файл recipes.json не найден!")
    except Exception as e:
        logging.error(f"Ошибка при чтении recipes.json: {e}")

load_recipes()

# --- ВЕБ-ЧАСТЬ ДЛЯ RENDER ---
@app.route('/')
def index():
    return "Vkusomer Bot is active!"

# --- СОСТОЯНИЯ ---
class Survey(StatesGroup):
    gender = State()
    goal = State()
    activity = State()
    age = State()
    height = State()
    weight = State()
    allergies = State()
    viewing_plan = State()

# --- КЛАВИАТУРЫ ---
start_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Погнали! 🚀")]], resize_keyboard=True)
gender_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
goal_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Поддерживать вес"), KeyboardButton(text="Набрать массу")]], resize_keyboard=True)
activity_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий образ жизни"), KeyboardButton(text="Средняя активность"), KeyboardButton(text="Высокая активность")]], resize_keyboard=True)

# --- ЛОГИКА ОПРЕДЕЛЕНИЯ БЛОКА ---
def get_user_block(goal, activity):
    mapping = {
        ("Похудеть", "Сидячий образ жизни"): "А",
        ("Похудеть", "Средняя активность"): "Б",
        ("Похудеть", "Высокая активность"): "В",
        ("Поддерживать вес", "Сидячий образ жизни"): "Г",
        ("Поддерживать вес", "Средняя активность"): "Д",
        ("Поддерживать вес", "Высокая активность"): "Е",
        ("Набрать массу", "Сидячий образ жизни"): "Ж",
        ("Набрать массу", "Средняя активность"): "З",
        ("Набрать массу", "Высокая активность"): "И",
    }
    return mapping.get((goal, activity), "А")

def generate_7_day_plan(user_block, user_allergens):
    suitable = [
        r for r in ALL_RECIPES 
        if user_block in r.get("blocks", []) 
        and not any(allrg in r.get("allergens", []) for allrg in user_allergens)
    ]
    
    br = [r for r in suitable if r['meal_type'] == 'breakfast']
    lu = [r for r in suitable if r['meal_type'] == 'lunch']
    di = [r for r in suitable if r['meal_type'] == 'dinner']

    if not br or not lu or not di: return None

    plan = []
    for i in range(1, 8):
        plan.append({
            "day": i,
            "meals": [random.choice(br), random.choice(lu), random.choice(di)]
        })
    return plan

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я — Вкусомер 🥗.\nТеперь мой демо-рацион рассчитан на **7 дней** с подробными инструкциями по готовке!\n\nДавай настроим твой профиль?",
        reply_markup=start_kb
    )

@dp.message(F.text == "Погнали! 🚀")
async def start_survey(message: types.Message, state: FSMContext):
    await message.answer("Выбери свой пол:", reply_markup=gender_kb)
    await state.set_state(Survey.gender)

@dp.message(Survey.gender, F.text.in_(["Мужской", "Женский"]))
async def proc_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Какая у тебя цель?", reply_markup=goal_kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal)
async def proc_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await message.answer("Твой уровень активности?", reply_markup=activity_kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity)
async def proc_act(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("Твой возраст (лет):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def proc_age(message: types.Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer("Твой рост (см):")
    await state.set_state(Survey.height)

@dp.message(Survey.height)
async def proc_h(message: types.Message, state: FSMContext):
    await state.update_data(height=message.text)
    await message.answer("Твой вес (кг):")
    await state.set_state(Survey.weight)

@dp.message(Survey.weight)
async def proc_w(message: types.Message, state: FSMContext):
    await state.update_data(weight=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Лактоза", callback_data="allg_lactose"), InlineKeyboardButton(text="❌ Глютен", callback_data="allg_gluten")],
        [InlineKeyboardButton(text="❌ Орехи", callback_data="allg_nuts"), InlineKeyboardButton(text="❌ Морепродукты", callback_data="allg_seafood")],
        [InlineKeyboardButton(text="✅ Готово / Я всё ем", callback_data="calc_7_days")]
    ])
    await message.answer("Есть ли ограничения в еде? Отметь или нажми 'Готово':", reply_markup=kb)
    await state.set_state(Survey.allergies)
    await state.update_data(allergies=[])

@dp.callback_query(F.data.startswith("allg_"))
async def proc_allg(callback: types.CallbackQuery, state: FSMContext):
    allg = callback.data.split("_")[1]
    data = await state.get_data()
    selected = data.get('allergies', [])
    if allg in selected: selected.remove(allg)
    else: selected.append(allg)
    await state.update_data(allergies=selected)
    await callback.answer(f"Обновлено: {allg}")

@dp.callback_query(F.data == "calc_7_days")
async def calculate_7(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    block = get_user_block(data['goal'], data['activity'])
    plan = generate_7_day_plan(block, data['allergies'])
    
    if not plan:
        return await callback.message.answer("К сожалению, под ваши фильтры пока нет рецептов. Попробуйте выбрать 'Я всё ем'.")
    
    await state.update_data(plan=plan)
    buttons = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
    buttons.append([InlineKeyboardButton(text="🛒 Весь список продуктов на 7 дней", callback_data="shop_all_7")])
    
    await callback.message.edit_text(
        f"✅ Твой план на 7 дней (Блок {block}) готов!\nНажми на нужный день, чтобы увидеть рецепты и инструкции:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(Survey.viewing_plan)

@dp.callback_query(F.data.startswith("day_"))
async def show_day(callback: types.CallbackQuery, state: FSMContext):
    day_num = int(callback.data.split("_")[1])
    data = await state.get_data()
    day_data = next(d for d in data['plan'] if d['day'] == day_num)
    
    msg = f"📅 **МЕНЮ: ДЕНЬ {day_num}**\n\n"
    for m in day_data['meals']:
        msg += f"🍴 **{m['meal_type'].upper()}: {m['name']}**\n"
        msg += f"🛒 *Ингредиенты:* {', '.join([i['name'] + ' (' + i['quantity'] + ')' for i in m['ingredients']])}\n"
        msg += f"👨‍🍳 *Как готовить:* {m['instructions']}\n"
        msg += f"⏱ {m['time']} мин | 🔥 {m['calories']} ккал\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к выбору дней", callback_data="back_to_days")]])
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "shop_all_7")
async def shop_all(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    plan = data.get('plan')
    
    full_list = {}
    for day in plan:
        for meal in day['meals']:
            for ing in meal['ingredients']:
                name = ing['name']
                if name in full_list: full_list[name].append(ing['quantity'])
                else: full_list[name] = [ing['quantity']]
    
    msg = "🛒 **ВАШ СПИСОК ПРОДУКТОВ НА 7 ДНЕЙ:**\n\n"
    for name, quantities in full_list.items():
        msg += f"— {name}: {', '.join(quantities)}\n"
    
    await callback.message.answer(msg, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_to_days")
async def back_days(callback: types.CallbackQuery):
    buttons = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
    buttons.append([InlineKeyboardButton(text="🛒 Весь список продуктов на 7 дней", callback_data="shop_all_7")])
    await callback.message.edit_text("Выбери день:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# --- ЗАПУСК ---
async def run_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, handle_signals=False)

def run_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())

threading.Thread(target=run_bot_in_thread, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
