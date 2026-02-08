# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import threading
import json
import random
from flask import Flask
from itertools import product

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardRemove
)

# --- НАСТРОЙКИ (ВАШИ ДАННЫЕ УЖЕ ЗДЕСЬ) ---
TOKEN = os.environ.get('TOKEN', "8585043014:AAG1dnEgTV65np--Bt0rAA9Wc64LiBta9FA")
TELEGRAM_CHANNEL_URL = "https://t.me/+YOEpXfsmd9tiODQ6"

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- УЛУЧШЕННАЯ ЗАГРУЗКА БАЗЫ РЕЦЕПТОВ ---
ALL_RECIPES = []
try:
    # Проверяем, существует ли файл, перед открытием
    if os.path.exists('recipes.json'):
        with open('recipes.json', 'r', encoding='utf-8') as f:
            ALL_RECIPES = json.load(f)
        logging.info(f"Успешно загружено {len(ALL_RECIPES)} рецептов из recipes.json.")
    else:
        logging.error("Файл recipes.json не найден! Бот будет работать, но не сможет подбирать меню.")
except json.JSONDecodeError:
    logging.error("Ошибка в синтаксисе файла recipes.json! Проверьте запятые и скобки.")
except Exception as e:
    logging.error(f"Произошла непредвиденная ошибка при чтении recipes.json: {e}")


# --- ВЕБ-ЧАСТЬ ДЛЯ "ПРОБУЖДЕНИЯ" ---
@app.route('/')
def index():
    return "Bot is alive and running!"

# --- (ОСТАЛЬНОЙ КОД БОТА БЕЗ ИЗМЕНЕНИЙ) ---
# ... (далее идет вся ваша логика, которую мы уже писали) ...
class Survey(StatesGroup):
    gender = State()
    goal = State()
    age = State()
    height = State()
    weight = State()
    activity = State()
    allergies = State()
    menu_generated = State()

start_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Погнали! 🚀")]], resize_keyboard=True)
gender_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
goal_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Поддерживать вес"), KeyboardButton(text="Набрать массу")]], resize_keyboard=True)
activity_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий образ жизни"), KeyboardButton(text="Средняя активность"), KeyboardButton(text="Высокая активность")]], resize_keyboard=True)

def generate_daily_menu(target_calories, user_allergens):
    if not ALL_RECIPES: return None
    available_recipes = [
        recipe for recipe in ALL_RECIPES 
        if not any(allergen in recipe.get("allergens", []) for allergen in user_allergens)
    ]
    breakfasts = [r for r in available_recipes if r['meal_type'] == 'breakfast']
    lunches = [r for r in available_recipes if r['meal_type'] == 'lunch']
    dinners = [r for r in available_recipes if r['meal_type'] == 'dinner']
    if not all([breakfasts, lunches, dinners]): return None
    best_combo, min_diff = None, float('inf')
    for b, l, d in product(breakfasts, lunches, dinners):
        current_calories = b['calories'] + l['calories'] + d['calories']
        diff = abs(current_calories - target_calories)
        if diff < min_diff:
            min_diff, best_combo = diff, [b, l, d]
    return best_combo

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я — Вкусомер 🥗.\n"
        "Твой карманный шеф-повар и диетолог. Я помогу тебе есть вкусно, худеть и при этом не проводить на кухне больше 15 минут.\n\n"
        "Давай настроим твой личный план?",
        reply_markup=start_kb
    )

@dp.message(F.text == "Погнали! 🚀")
async def start_survey(message: types.Message, state: FSMContext):
    await message.answer("Выбери свой пол:", reply_markup=gender_kb)
    await state.set_state(Survey.gender)

@dp.message(Survey.gender, F.text.in_(["Мужской", "Женский"]))
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Какая у тебя цель?", reply_markup=goal_kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal, F.text.in_(["Похудеть", "Поддерживать вес", "Набрать массу"]))
async def process_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await message.answer("Какой у тебя уровень активности?", reply_markup=activity_kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity, F.text.in_(["Сидячий образ жизни", "Средняя активность", "Высокая активность"]))
async def process_activity(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("Введи свой возраст (полных лет):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not (10 < int(message.text) < 100):
        await message.answer("Пожалуйста, введи возраст цифрами (от 10 до 100).")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Введи свой рост (в см):")
    await state.set_state(Survey.height)

@dp.message(Survey.height)
async def process_height(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not (100 < int(message.text) < 250):
        await message.answer("Пожалуйста, введи рост цифрами (в см).")
        return
    await state.update_data(height=int(message.text))
    await message.answer("Введи свой вес (в кг, можно через точку, например 65.5):")
    await state.set_state(Survey.weight)

@dp.message(Survey.weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(',', '.'))
        if not (30 < weight < 200): raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи вес корректно (например, 65.5).")
        return
    await state.update_data(weight=weight)
    allergies_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Лактоза", callback_data="allergy_lactose")],
        [InlineKeyboardButton(text="❌ Глютен", callback_data="allergy_gluten")],
        [InlineKeyboardButton(text="❌ Орехи", callback_data="allergy_nuts")],
        [InlineKeyboardButton(text="❌ Морепродукты", callback_data="allergy_seafood")],
        [InlineKeyboardButton(text="✅ Я всё ем", callback_data="allergy_none")],
        [InlineKeyboardButton(text="➡️ Показать результат", callback_data="calculate_result")]
    ])
    await message.answer("Безопасность превыше всего! Есть ли продукты, которые тебе нельзя? Отметь их и нажми 'Показать результат'.", reply_markup=allergies_kb)
    await state.set_state(Survey.allergies)
    await state.update_data(allergies=[])

@dp.callback_query(Survey.allergies, F.data.startswith("allergy_"))
async def process_allergies(callback: types.CallbackQuery, state: FSMContext):
    allergy = callback.data.split("_")[1]
    user_data = await state.get_data()
    if allergy == "none": user_data['allergies'] = []
    elif allergy in user_data['allergies']: user_data['allergies'].remove(allergy)
    else: user_data['allergies'].append(allergy)
    await state.update_data(allergies=user_data['allergies'])
    await callback.answer(f"Выбор обновлен. Текущие исключения: {', '.join(user_data['allergies']) or 'нет'}")

@dp.callback_query(Survey.allergies, F.data == "calculate_result")
async def calculate_result(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brm = (10 * data['weight']) + (6.25 * data['height']) - (5 * data['age'])
    brm += 5 if data['gender'] == "Мужской" else -161
    activity_coeffs = {"Сидячий образ жизни": 1.2, "Средняя активность": 1.55, "Высокая активность": 1.725}
    calories = brm * activity_coeffs[data['activity']]
    if data['goal'] == "Похудеть": calories -= 400
        elif data['goal'] == "Набрать массу": calories += 400
    daily_menu = generate_daily_menu(calories, data.get('allergies', []))
    if not daily_menu:
        await callback.message.edit_text("К сожалению, с вашими ограничениями мы не смогли подобрать меню из нашей базы. Попробуйте убрать некоторые аллергены или попробуйте позже, мы постоянно добавляем новые рецепты!")
        await state.clear()
        return
    total_menu_calories = sum(r['calories'] for r in daily_menu)
    await state.update_data(generated_menu=daily_menu)
    await callback.message.edit_text(
        f"Твоя цель: {int(calories)} ккал.\nМы подобрали для тебя меню на {total_menu_calories} ккал.\n\nВсе рецепты готовятся до 25 минут.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Посмотреть меню на сегодня 🍽", callback_data="show_menu")]])
    )
    await state.set_state(Survey.menu_generated)

@dp.callback_query(Survey.menu_generated, F.data == "show_menu")
async def show_menu(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    menu = data.get('generated_menu')
    if not menu:
        await callback.answer("Ошибка: меню не найдено. Пожалуйста, начните заново /start", show_alert=True)
        return
    menu_text = "🍽 **Меню на сегодня:**\n\n"
    for recipe in menu:
        menu_text += f"**{recipe['meal_type'].capitalize()}:** {recipe['name']} ({recipe['time']} мин).\n"
    await callback.message.answer(
        menu_text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Сформировать список покупок", callback_data="shop_list")]])
    )
    await callback.answer()

@dp.callback_query(Survey.menu_generated, F.data == "shop_list")
async def show_shop_list(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    menu = data.get('generated_menu')
    if not menu:
        await callback.answer("Ошибка: меню не найдено. Пожалуйста, начните заново /start", show_alert=True)
        return
    shopping_list = {}
    for recipe in menu:
        for ingredient in recipe['ingredients']:
            name, quantity = ingredient['name'], ingredient['quantity']
            if name in shopping_list: shopping_list[name] += f", {quantity}"
            else: shopping_list[name] = quantity
    shop_list_text = "🛒 **Вот твой список покупок на сегодня:**\n\n"
    for name, quantity in shopping_list.items():
        shop_list_text += f"— {name} ({quantity})\n"
    await callback.message.answer(shop_list_text, parse_mode="Markdown")
    await asyncio.sleep(2)
    await callback.message.answer(
        "Понравилось? Это был лишь демо-день!\nЧтобы получать готовый план на неделю, подпишись на наш закрытый клуб.\n\nА пока загляни на наш основной канал с лайфхаками быстрой готовки!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти в канал 'Вкусомер' 📢", url=TELEGRAM_CHANNEL_URL)],
            [InlineKeyboardButton(text="Оформить подписку (290 руб/мес)", callback_data="subscribe")]
        ])
    )
    await callback.answer()
    await state.clear()

@dp.callback_query(F.data == "subscribe")
async def process_subscribe(callback: types.CallbackQuery):
    await callback.answer("Функция оплаты скоро будет добавлена!", show_alert=True)

async def run_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if name == "__main__":
    bot_thread = threading.Thread(target=lambda: asyncio.run(run_bot()))
    bot_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
