# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import threading
import json
import random
import re
import sqlite3
from datetime import datetime
from flask import Flask
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, 
    InlineKeyboardMarkup, InlineKeyboardButton
)

# --- НАСТРОЙКИ ---
TOKEN = "8585043014:AAFQsH6ESYByucOgXq07WttwnYW4Pp0Vh78"
TG_CHANNEL = "https://t.me/+YOEpXfsmd9tiODQ6"
PLUS_BOT = "https://t.me/TasteMeterPlus_bot"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- ЗАГРУЗКА РЕЦЕПТОВ ---
ALL_RECIPES = []
try:
    if os.path.exists('recipes.json'):
        with open('recipes.json', 'r', encoding='utf-8') as f:
            ALL_RECIPES = json.load(f)
except Exception as e:
    logging.error(f"Ошибка загрузки JSON: {e}")

# --- СОСТОЯНИЯ ---
class Survey(StatesGroup):
    gender = State()
    goal = State()
    target_w = State()
    activity = State()
    age = State()
    height = State()
    weight = State()
    allergies = State()

# --- ЛОГИКА СУММИРОВАНИЯ ПРОДУКТОВ ---
def aggregate_ingredients(plan):
    shopping_list = {}
    for day in plan:
        for meal in day['meals']:
            for ing in meal['ingredients']:
                name = ing['name'].lower().strip()
                qty_str = str(ing['quantity']).lower().strip()
                
                # Ищем число в строке (например "2 шт" или "150г")
                match = re.search(r"(\d+[\.,]?\d*)", qty_str)
                unit = re.sub(r"(\d+[\.,]?\d*)", "", qty_str).strip()
                
                if match:
                    val = float(match.group(1).replace(",", "."))
                    if name not in shopping_list:
                        shopping_list[name] = {"val": val, "unit": unit}
                    else:
                        if shopping_list[name]["unit"] == unit:
                            shopping_list[name]["val"] += val
                        else:
                            # Если единицы разные (г и шт), просто дописываем рядом
                            shopping_list[name]["val"] = f"{shopping_list[name]['val']} {shopping_list[name]['unit']} + {val}"
                else:
                    # Если чисел нет, просто сохраняем текст
                    shopping_list[name] = {"val": qty_str, "unit": ""}
    
    return shopping_list

# --- ЛОГИКА БЛОКОВ ---
def get_user_block(goal, activity):
    mapping = {
        ("Похудеть", "Сидячий"): "А", ("Похудеть", "Средний"): "Б", ("Похудеть", "Высокий"): "В",
        ("Поддерживать вес", "Сидячий"): "Г", ("Поддерживать вес", "Средний"): "Д", ("Поддерживать вес", "Высокий"): "Е",
        ("Набрать массу", "Сидячий"): "Ж", ("Набрать массу", "Средний"): "З", ("Набрать массу", "Высокий"): "И"
    }
    return mapping.get((goal, activity), "А")

def generate_7_day_plan(user_block, user_allergens):
    suitable = [
        r for r in ALL_RECIPES 
        if user_block in r.get("blocks", []) 
        and not any(allrg in r.get("allergens", []) for allrg in user_allergens)
    ]
    if not suitable: suitable = ALL_RECIPES
    
    br = [r for r in suitable if r['meal_type'] == 'breakfast']
    lu = [r for r in suitable if r['meal_type'] == 'lunch']
    di = [r for r in suitable if r['meal_type'] == 'dinner']
    
    if not br or not lu or not di: return None
    plan = []
    for i in range(1, 8):
        plan.append({"day": i, "meals": [random.choice(br), random.choice(lu), random.choice(di)]})
    return plan

# --- ОБРАБОТЧИКИ ---

@app.route('/')
def index(): return "OK"

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("✨ Привет! Давай настроим твой рацион.\n\nТвой пол? 👤", reply_markup=kb)
    await state.set_state(Survey.gender)

@dp.message(Survey.gender)
async def proc_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Набрать массу"), KeyboardButton(text="Поддерживать вес")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🎯 Какая наша цель?", reply_markup=kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal)
async def proc_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    if message.text in ["Похудеть", "Набрать массу"]:
        await message.answer("🏁 Какой вес твоя цель? (кг)", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Survey.target_w)
    else:
        await state.set_state(Survey.activity)
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий"), KeyboardButton(text="Средний"), KeyboardButton(text="Высокий")]], resize_keyboard=True, one_time_keyboard=True)
        await message.answer("🏃‍♂️ Твоя активность?", reply_markup=kb)

@dp.message(Survey.target_w)
async def proc_tw(message: types.Message, state: FSMContext):
    await state.update_data(target_w=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий"), KeyboardButton(text="Средний"), KeyboardButton(text="Высокий")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🏃‍♂️ Твоя активность?", reply_markup=kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity)
async def proc_act(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("🎂 Твой возраст?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def proc_age(message: types.Message, state: FSMContext):
    await state.update_data(age=int(message.text))
    await message.answer("📏 Твой рост (см)?")
    await state.set_state(Survey.height)

@dp.message(Survey.height)
async def proc_h(message: types.Message, state: FSMContext):
    await state.update_data(height=int(message.text))
    await message.answer("⚖️ Твой текущий вес (кг)?")
    await state.set_state(Survey.weight)

@dp.message(Survey.weight)
async def proc_w(message: types.Message, state: FSMContext):
    await state.update_data(weight=int(message.text))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Лактоза", callback_data="allg_lactose"), InlineKeyboardButton(text="❌ Глютен", callback_data="allg_gluten")],
        [InlineKeyboardButton(text="✅ У меня нет аллергий / Готово", callback_data="allg_done")]
    ])
    await message.answer("⚠️ Есть ли у тебя аллергии или ограничения?", reply_markup=kb)
    await state.set_state(Survey.allergies)
    await state.update_data(user_allg=[])

@dp.callback_query(F.data.startswith("allg_"))
async def proc_allg(call: types.CallbackQuery, state: FSMContext):
    if call.data == "allg_done":
        data = await state.get_data()
        # Расчет нормы
        bmr = (10 * data['weight']) + (6.25 * data['height']) - (5 * data['age']) + (5 if data['gender'] == "Мужской" else -161)
        norma = int(bmr * 1.3)
        if data['goal'] == "Похудеть": norma -= 400
        
        plan = generate_7_day_plan(get_user_block(data['goal'], data['activity']), data['user_allg'])
        await state.update_data(plan=plan, norma=norma)
        
        await call.message.answer("✅ **Твой профиль успешно создан! Тест пройден.**")
        btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
        btns.append([InlineKeyboardButton(text="🛒 Список продуктов на 7 дней", callback_data="shop_7")])
        await call.message.answer(f"Твоя норма: **{norma} ккал**. План на неделю готов!", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        allg = call.data.replace("allg_", "")
        d = await state.get_data()
        current = d['user_allg']
        if allg not in current: current.append(allg)
        await state.update_data(user_allg=current)
        await call.answer(f"Добавлено ограничение: {allg}")

# --- КНОПКИ ДНЕЙ ---

@dp.callback_query(F.data.startswith("day_"))
async def show_day(call: types.CallbackQuery, state: FSMContext):
    day_num = int(call.data.split("_")[1])
    data = await state.get_data()
    day_data = data['plan'][day_num-1]
    msg = f"📅 **ДЕНЬ {day_num} (Цель: {data['norma']} ккал)**\n\n"
    btns = []
    for idx, m in enumerate(day_data['meals']):
        msg += f"🍴 **{m['meal_type'].upper()}**: {m['name']} ({m['calories']} ккал)\n"
        btns.append([InlineKeyboardButton(text=f"👨‍🍳 Рецепт: {m['name']}", callback_data=f"rec_{day_num}_{idx}")])
    btns.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_days")])
    await call.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("rec_"))
async def show_rec(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    d_n, m_idx = int(parts[1]), int(parts[2])
    data = await state.get_data()
    meal = data['plan'][d_n-1]['meals'][m_idx]
    txt = f"👨‍🍳 **{meal['name']}**\n\n**Ингредиенты:**\n" + "\n".join([f"- {i['name']} ({i['quantity']})" for i in meal['ingredients']]) + f"\n\n**Инструкция:**\n{meal['instructions']}"
    await call.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"day_{d_n}")]]))

@dp.callback_query(F.data == "shop_7")
async def shop_7(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ingredients = aggregate_ingredients(data['plan'])
    txt = "🛒 **СПИСОК НА 7 ДНЕЙ (ОБЪЕДИНЕННЫЙ):**\n\n"
    for name, info in ingredients.items():
        val = info['val']
        if isinstance(val, float):
            # Если число круглое (2.0), убираем точку
            val = int(val) if val.is_integer() else val
        txt += f"— {name.capitalize()}: {val} {info['unit']}\n"
    
    txt += f"\n\n📢 Канал: {TG_CHANNEL}\n💎 Продвинутый ИИ-Диетолог: {PLUS_BOT}"
    await call.message.answer(txt)
    await call.answer()

@dp.callback_query(F.data == "back_days")
async def back_days(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
    btns.append([InlineKeyboardButton(text="🛒 Список продуктов на 7 дней", callback_data="shop_7")])
    await call.message.edit_text(f"Выбери день (Норма: {data['norma']} ккал):", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# --- ЗАПУСК ---
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), use_reloader=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
