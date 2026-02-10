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
TOKEN = "8585043014:AAFQsH6ESYByucOgXq07WttwnYW4Pp0Vh78"
TELEGRAM_CHANNEL_URL = "https://t.me/+YOEpXfsmd9tiODQ6"
PAID_BOT_URL = "https://t.me/TasteMeterPlus_bot"

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
            logging.info(f"✅ Загружено {len(ALL_RECIPES)} рецептов.")
    except Exception as e:
        logging.error(f"❌ Ошибка JSON: {e}")

load_recipes()

# --- ВЕБ-ЧАСТЬ ДЛЯ RENDER ---
@app.route('/')
def index():
    return "Vkusomer Bot is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- ЛОГИКА БЛОКОВ ---
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
    clean_allergens = [a.replace("allg_", "") for a in user_allergens]
    suitable = [
        r for r in ALL_RECIPES 
        if user_block in r.get("blocks", []) 
        and not any(allrg in r.get("allergens", []) for allrg in clean_allergens)
    ]
    if len(suitable) < 5: # Резервный поиск
        suitable = [r for r in ALL_RECIPES if not any(allrg in r.get("allergens", []) for allrg in clean_allergens)]

    br = [r for r in suitable if r['meal_type'] == 'breakfast']
    lu = [r for r in suitable if r['meal_type'] == 'lunch']
    di = [r for r in suitable if r['meal_type'] == 'dinner']
    if not br or not lu or not di: return None
    plan = []
    for i in range(1, 8):
        plan.append({"day": i, "meals": [random.choice(br), random.choice(lu), random.choice(di)]})
    return plan

# --- СОСТОЯНИЯ ---
class Survey(StatesGroup):
    gender, goal, activity, age, height, weight, allergies, viewing_plan = [State() for _ in range(8)]

start_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Погнали! 🚀")]], resize_keyboard=True)
gender_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
goal_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Поддерживать вес"), KeyboardButton(text="Набрать массу")]], resize_keyboard=True)
activity_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий образ жизни"), KeyboardButton(text="Средняя активность"), KeyboardButton(text="Высокая активность")]], resize_keyboard=True)

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Я — Вкусомер 🥗.\nДавай составим план на 7 дней!", reply_markup=start_kb)

@dp.message(F.text == "Погнали! 🚀")
async def start_survey(message: types.Message, state: FSMContext):
    await message.answer("Выбери пол:", reply_markup=gender_kb)
    await state.set_state(Survey.gender)

@dp.message(Survey.gender)
async def proc_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Твоя цель?", reply_markup=goal_kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal)
async def proc_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await message.answer("Активность?", reply_markup=activity_kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity)
async def proc_act(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("Твой возраст:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def proc_age(message: types.Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer("Рост (см):")
    await state.set_state(Survey.height)

@dp.message(Survey.height)
async def proc_h(message: types.Message, state: FSMContext):
    await state.update_data(height=message.text)
    await message.answer("Вес (кг):")
    await state.set_state(Survey.weight)

@dp.message(Survey.weight)
async def proc_w(message: types.Message, state: FSMContext):
    await state.update_data(weight=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Лактоза", callback_data="allg_lactose"), InlineKeyboardButton(text="❌ Глютен", callback_data="allg_gluten")],
        [InlineKeyboardButton(text="❌ Морепродукты", callback_data="allg_seafood"), InlineKeyboardButton(text="✅ Готово / Я всё ем", callback_data="calc_7_days")]
    ])
    await message.answer("Есть ограничения в еде?", reply_markup=kb)
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
    await callback.answer(f"Выбрано: {allg}")

@dp.callback_query(F.data == "calc_7_days")
async def calculate_result(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        w, h, a = float(str(data['weight']).replace(',', '.')), float(data['height']), float(data['age'])
        bmr = (10 * w) + (6.25 * h) - (5 * a) + (5 if data['gender'] == "Мужской" else -161)
        cals = int(bmr * {"Сидячий образ жизни": 1.2, "Средняя активность": 1.55, "Высокая активность": 1.725}.get(data['activity'], 1.2))
        if data['goal'] == "Похудеть": cals -= 400
        elif data['goal'] == "Набрать массу": cals += 400
    except: return await callback.message.answer("Ошибка в данных. Нажми /start")

    block = get_user_block(data['goal'], data['activity'])
    plan = generate_7_day_plan(block, data['allergies'])
    if not plan: return await callback.message.answer("Рецептов скоро будет больше!")

    await state.update_data(plan=plan)
    btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"v_day_{i}")] for i in range(1, 8)]
    btns.append([InlineKeyboardButton(text="🛒 Список продуктов на 7 дней", callback_data="shop_7")])
    await callback.message.edit_text(f"✅ Норма: {cals} ккал. План (Блок {block}) готов!", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    await state.set_state(Survey.viewing_plan)

@dp.callback_query(F.data.startswith("v_day_"))
async def show_day(callback: types.CallbackQuery, state: FSMContext):
    day_num = int(callback.data.split("_")[2])
    data = await state.get_data()
    day_data = data['plan'][day_num-1]
    msg = f"📅 **ДЕНЬ {day_num}**\n\n"
    btns = []
    for idx, m in enumerate(day_data['meals']):
        msg += f"🍴 **{m['meal_type'].upper()}**: {m['name']} ({m['calories']} ккал)\n"
        btns.append([InlineKeyboardButton(text=f"👨‍🍳 Рецепт: {m['meal_type'].capitalize()}", callback_data=f"rec_{day_num}_{idx}")])
    btns.append([InlineKeyboardButton(text="⬅️ Назад к дням", callback_data="back_days")])
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("rec_"))
async def show_rec(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    d_n, m_idx = int(parts[1]), int(parts[2])
    data = await state.get_data()
    meal = data['plan'][d_n-1]['meals'][m_idx]
    txt = f"👨‍🍳 **{meal['name']}**\n\n**Ингредиенты:**\n" + "\n".join([f"- {i['name']} ({i['quantity']})" for i in meal['ingredients']]) + f"\n\n**Как готовить:**\n{meal['instructions']}"
    await callback.message.edit_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"v_day_{d_n}")]]))

@dp.callback_query(F.data == "shop_7")
async def shop_7(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    full_list = {}
    for day in data['plan']:
        for meal in day['meals']:
            for ing in meal['ingredients']:
                full_list[ing['name']] = full_list.get(ing['name'], []) + [ing['quantity']]
    
    txt = "🛒 **СПИСОК НА 7 ДНЕЙ:**\n\n" + "\n".join([f"- **{n}**: {', '.join(q)}" for n, q in full_list.items()])
    await callback.message.answer(txt, parse_mode="Markdown")
    
    # ССЫЛКИ ПОСЛЕ СПИСКА
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал 'Вкусомер'", url=TELEGRAM_CHANNEL_URL)],
        [InlineKeyboardButton(text="💎 Подписка TasteMeter+", url=PAID_BOT_URL)]
    ])
    await callback.message.answer("Понравилось? Это был лишь демо-день!\nЧтобы получить план на неделю и больше рецептов, подпишись на наши ресурсы:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "back_days")
async def back_days_handler(callback: types.CallbackQuery):
    btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"v_day_{i}")] for i in range(1, 8)]
    btns.append([InlineKeyboardButton(text="🛒 Список продуктов на 7 дней", callback_data="shop_7")])
    await callback.message.edit_text("Выбери день:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# --- ЗАПУСК ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
