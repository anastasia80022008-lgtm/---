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
# Токен вашего бота
TOKEN = "8585043014:AAFQsH6ESYByucOgXq07WttwnYW4Pp0Vh78"
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
            logging.info(f"✅ Успешно загружено {len(ALL_RECIPES)} рецептов.")
        else:
            logging.error("❌ ОШИБКА: Файл recipes.json не найден!")
    except Exception as e:
        logging.error(f"❌ ОШИБКА при чтении JSON: {e}")

load_recipes()

# --- ВЕБ-ЧАСТЬ ДЛЯ RENDER (Keep-Alive) ---
@app.route('/')
def index():
    return "Бот 'Вкусомер' запущен и работает!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    # Запуск сервера Flask
    app.run(host='0.0.0.0', port=port, use_reloader=False)

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
    # Фильтруем рецепты по блоку и аллергиям
    suitable = [
        r for r in ALL_RECIPES 
        if user_block in r.get("blocks", []) 
        and not any(allrg in r.get("allergens", []) for allrg in user_allergens)
    ]
    
    br = [r for r in suitable if r['meal_type'] == 'breakfast']
    lu = [r for r in suitable if r['meal_type'] == 'lunch']
    di = [r for r in suitable if r['meal_type'] == 'dinner']

    if not br or not lu or not di:
        return None

    plan = []
    for i in range(1, 8):
        # Выбираем случайные блюда на каждый день
        plan.append({
            "day": i,
            "meals": [random.choice(br), random.choice(lu), random.choice(di)]
        })
    return plan

# --- СОСТОЯНИЯ АНКЕТЫ ---
class Survey(StatesGroup):
    gender = State()
    goal = State()
    activity = State()
    age = State()
    height = State()
    weight = State()
    allergies = State()
    viewing_plan = State()

# Клавиатуры
start_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Погнали! 🚀")]], resize_keyboard=True)
gender_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
goal_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Поддерживать вес"), KeyboardButton(text="Набрать массу")]], resize_keyboard=True)
activity_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий образ жизни"), KeyboardButton(text="Средняя активность"), KeyboardButton(text="Высокая активность")]], resize_keyboard=True)

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я — Вкусомер 🥗.\nТеперь мой демо-рацион рассчитан на **7 дней** с подробными инструкциями!\n\nДавай настроим твой профиль?",
        reply_markup=start_kb
    )

@dp.message(F.text == "Погнали! 🚀")
async def start_survey(message: types.Message, state: FSMContext):
    await message.answer("Выбери свой пол:", reply_markup=gender_kb)
    await state.set_state(Survey.gender)

@dp.message(Survey.gender)
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
    await message.answer("Введи свой возраст (лет):", reply_markup=ReplyKeyboardRemove())
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
    await message.answer("Есть ли ограничения в еде? Отметь нужные и нажми 'Готово':", reply_markup=kb)
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
    await callback.answer(f"Выбор обновлен: {allg}")

@dp.callback_query(F.data == "calc_7_days")
async def calculate_7_days(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # 1. ТОЧНЫЙ РАСЧЕТ КАЛОРИЙ (Миффлин-Сан Жеор)
    w, h, a = float(str(data['weight']).replace(',', '.')), float(data['height']), float(data['age'])
    bmr = (10 * w) + (6.25 * h) - (5 * a) + (5 if data['gender'] == "Мужской" else -161)
    
    c_map = {"Сидячий образ жизни": 1.2, "Средняя активность": 1.55, "Высокая активность": 1.725}
    calories = bmr * c_map.get(data['activity'], 1.2)
    
    if data['goal'] == "Похудеть": calories -= 400
    elif data['goal'] == "Набрать массу": calories += 400
    
    # 2. ГЕНЕРАЦИЯ ПЛАНА
    block = get_user_block(data['goal'], data['activity'])
    plan = generate_7_day_plan(block, data['allergies'])
    
    if not plan:
        return await callback.message.answer("К сожалению, под ваши фильтры пока нет рецептов. Попробуйте убрать аллергии.")

    await state.update_data(plan=plan, target_calories=int(calories))
    
    # Кнопки выбора дней
    btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"view_day_{i}")] for i in range(1, 8)]
    btns.append([InlineKeyboardButton(text="🛒 Список продуктов на 7 дней", callback_data="shop_7_all")])
    
    await callback.message.edit_text(
        f"✅ Твой расчет готов: *{int(calories)} ккал/день*.\n\n"
        f"Я составил меню на 7 дней (Блок {block}).\nНажми на день, чтобы увидеть блюда и рецепты:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )
    await state.set_state(Survey.viewing_plan)

@dp.callback_query(F.data.startswith("view_day_"))
async def show_day(callback: types.CallbackQuery, state: FSMContext):
    day_num = int(callback.data.split("_")[2])
    data = await state.get_data()
    day_data = next(d for d in data['plan'] if d['day'] == day_num)
    
    msg = f"📅 **МЕНЮ: ДЕНЬ {day_num}**\n\n"
    btns = []
    
    for idx, m in enumerate(day_data['meals']):
        msg += f"🍴 **{m['meal_type'].upper()}**: {m['name']}\n"
        msg += f"⏱ {m['time']} мин | 🔥 {m['calories']} ккал\n\n"
        btns.append([InlineKeyboardButton(text=f"👨‍🍳 Рецепт: {m['meal_type'].capitalize()}", callback_data=f"recipe_{day_num}_{idx}")])
    
    btns.append([InlineKeyboardButton(text="⬅️ Назад к выбору дней", callback_data="back_to_plan")])
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("recipe_"))
async def show_recipe(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    d_num, m_idx = int(parts[1]), int(parts[2])
    data = await state.get_data()
    meal = data['plan'][d_num-1]['meals'][m_idx]
    
    text = f"👨‍🍳 **РЕЦЕПТ: {meal['name'].upper()}**\n\n"
    text += "**Ингредиенты:**\n"
    for ing in meal['ingredients']:
        text += f"— {ing['name']} ({ing['quantity']})\n"
    text += f"\n**Как готовить:**\n{meal['instructions']}"
    
    kb = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_day_{d_num}")]]
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "shop_7_all")
async def show_full_shop_list(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    full_list = {}
    for day in data['plan']:
        for meal in day['meals']:
            for ing in meal['ingredients']:
                name = ing['name']
                full_list[name] = full_list.get(name, []) + [ing['quantity']]
    
    txt = "🛒 **СПИСОК ПРОДУКТОВ НА 7 ДНЕЙ:**\n\n"
    for name, qty in full_list.items():
        txt += f"— {name}: {', '.join(qty)}\n"
    
    await callback.message.answer(txt, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_to_plan")
async def back_to_plan(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"view_day_{i}")] for i in range(1, 8)]
    btns.append([InlineKeyboardButton(text="🛒 Список продуктов на 7 дней", callback_data="shop_7_all")])
    await callback.message.edit_text("Выбери день:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# --- ЗАПУСК ---
async def run_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    # handle_signals=False нужен, чтобы не было ошибки потоков на Render
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    # 1. Запускаем веб-сервер в фоне
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Запускаем бота
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
