# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import threading
import json
import random
import re
from flask import Flask

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
if os.path.exists('recipes.json'):
    with open('recipes.json', 'r', encoding='utf-8') as f:
        ALL_RECIPES = json.load(f)

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

# --- УМНАЯ ЛОГИКА СУММИРОВАНИЯ ---
def aggregate_ingredients(plan):
    shopping_list = {}
    for day in plan:
        for meal in day['meals']:
            for ing in meal['ingredients']:
                name = ing['name'].lower().strip()
                qty_str = str(ing['quantity']).lower().strip()
                
                # Ищем цифры (целые или дробные)
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
                            shopping_list[name]["val"] = f"{shopping_list[name]['val']} {shopping_list[name]['unit']} + {val}"
                else:
                    shopping_list[name] = {"val": qty_str, "unit": ""}
    return shopping_list

# --- ЛОГИКА ОПРЕДЕЛЕНИЯ БЛОКА ---
def get_user_block(goal, activity):
    mapping = {
        ("Похудеть", "Сидячий"): "А", ("Похудеть", "Средний"): "Б", ("Похудеть", "Высокий"): "В",
        ("Поддерживать вес", "Сидячий"): "Г", ("Поддерживать вес", "Средний"): "Д", ("Поддерживать вес", "Высокий"): "Е",
        ("Набрать массу", "Сидячий"): "Ж", ("Набрать массу", "Средний"): "З", ("Набрать массу", "Высокий"): "И"
    }
    return mapping.get((goal, activity), "А")

# --- ОБРАБОТЧИКИ ---

@app.route('/')
def index(): return "Бот работает"

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome = (
        "Добро пожаловать во Вкусомер! 🥗\n\n"
        "Я помогу тебе составить план питания на ближайшие 7 дней. В этой версии я использую готовую базу рецептов, "
        "чтобы ты мог быстро начать свой путь к здоровью.\n\n"
        "Что ты получишь сейчас:\n"
        "— Расчет твоей индивидуальной нормы калорий.\n"
        "— Готовое меню на неделю, которое не повторяется.\n"
        "— Список продуктов для магазина, где все ингредиенты уже сложены за тебя.\n\n"
        "А в нашей Плюс-версии тебе будет помогать настоящий Искусственный Интеллект: он умеет считать калории по фото твоей тарелки, "
        "общаться с тобой как личный психолог и придумывать рецепты из любых остатков в холодильнике!\n\n"
        "Давай начнем с настройки твоего профиля. Укажи свой пол: 👤"
    )
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
    await message.answer(welcome, reply_markup=kb)
    await state.set_state(Survey.gender)

@dp.message(Survey.gender)
async def proc_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Набрать массу"), KeyboardButton(text="Поддерживать вес")]], resize_keyboard=True)
    await message.answer("Понял тебя. Какая у нас сейчас главная цель? 🎯", reply_markup=kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal)
async def proc_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    if message.text in ["Похудеть", "Набрать массу"]:
        await message.answer("Это отличная цель! К какому весу в идеале мы хотим прийти? Напиши цифру в килограммах: 🏁", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Survey.target_w)
    else:
        await state.set_state(Survey.activity)
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий"), KeyboardButton(text="Средний"), KeyboardButton(text="Высокий")]], resize_keyboard=True)
        await message.answer("Как много ты двигаешься в течение дня? Выбери свой уровень активности: 🏃‍♂️", reply_markup=kb)

@dp.message(Survey.target_w)
async def proc_tw(message: types.Message, state: FSMContext):
    await state.update_data(target_w=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Сидячий"), KeyboardButton(text="Средний"), KeyboardButton(text="Высокий")]], resize_keyboard=True)
    await message.answer("Принято. Теперь укажи свой уровень физической активности: 🏃‍♂️", reply_markup=kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity)
async def proc_act(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("Сколько тебе полных лет? Напиши числом: 🎂", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def proc_age(message: types.Message, state: FSMContext):
    await state.update_data(age=int(message.text))
    await message.answer("Какой у тебя рост в сантиметрах? 📏")
    await state.set_state(Survey.height)

@dp.message(Survey.height)
async def proc_h(message: types.Message, state: FSMContext):
    await state.update_data(height=int(message.text))
    await message.answer("И последний шаг: твой текущий вес в килограммах? ⚖️")
    await state.set_state(Survey.weight)

@dp.message(Survey.weight)
async def proc_w(message: types.Message, state: FSMContext):
    await state.update_data(weight=int(message.text))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Лактоза", callback_data="allg_lactose"), InlineKeyboardButton(text="❌ Глютен", callback_data="allg_gluten")],
        [InlineKeyboardButton(text="✅ У меня нет аллергий / Готово", callback_data="allg_done")]
    ])
    await message.answer("Есть ли у тебя какие-то аллергии или ограничения в еде? Отметь их или нажми Готово: ⚠️", reply_markup=kb)
    await state.set_state(Survey.allergies)
    await state.update_data(user_allg=[])

@dp.callback_query(F.data.startswith("allg_"))
async def proc_allg(call: types.CallbackQuery, state: FSMContext):
    if call.data == "allg_done":
        data = await state.get_data()
        # Расчет калорий
        w, h, a, gen = data['weight'], data['height'], data['age'], data['gender']
        bmr = (10 * w) + (6.25 * h) - (5 * a) + (5 if gen == "Мужской" else -161)
        norma = int(bmr * 1.3)
        if data['goal'] == "Похудеть": norma -= 400
        
        # Генерация плана
        block = get_user_block(data['goal'], data['activity'])
        allgs = data['user_allg']
        suitable = [r for r in ALL_RECIPES if block in r.get("blocks", []) and not any(a in r.get("allergens", []) for a in allgs)]
        if not suitable: suitable = ALL_RECIPES
        
        br = [r for r in suitable if r['meal_type'] == 'breakfast']
        lu = [r for r in suitable if r['meal_type'] == 'lunch']
        di = [r for r in suitable if r['meal_type'] == 'dinner']
        
        plan = [{"day": i, "meals": [random.choice(br), random.choice(lu), random.choice(di)]} for i in range(1, 8)]
        await state.update_data(plan=plan, norma=norma)
        
        await call.message.answer("✅ Тест успешно пройден! Твой профиль создан.")
        
        res_text = (
            f"Твоя индивидуальная норма калорий составляет {norma} ккал в день. "
            f"Для твоей цели {data['goal']} я подобрал оптимальный рацион на неделю из нашей базы.\n\n"
            "Помни, что в Плюс-версии нашего бота (ссылка в конце) расчеты делает Искусственный Интеллект, "
            "который подстраивается под твои вкусы в реальном времени!\n\n"
            "Выбери день, чтобы посмотреть меню:"
        )
        
        btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
        btns.append([InlineKeyboardButton(text="🛒 Список продуктов на неделю", callback_data="shop_7")])
        await call.message.answer(res_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        allg = call.data.replace("allg_", "")
        d = await state.get_data(); current = d['user_allg']
        if allg not in current: current.append(allg)
        await state.update_data(user_allg=current); await call.answer(f"Ограничение добавлено: {allg}")

# --- МЕНЮ ДНЯ ---

@dp.callback_query(F.data.startswith("day_"))
async def show_day(call: types.CallbackQuery, state: FSMContext):
    day_num = int(call.data.split("_")[1])
    data = await state.get_data(); day_data = data['plan'][day_num-1]
    
    msg = f"Меню на день {day_num}. Твоя цель сегодня — {data['norma']} ккал.\n\n"
    btns = []
    for idx, m in enumerate(day_data['meals']):
        msg += f"🍴 {m['meal_type'].upper()}: {m['name']} ({m['calories']} ккал)\n"
        btns.append([InlineKeyboardButton(text=f"Рецепт: {m['name']}", callback_data=f"rec_{day_num}_{idx}")])
    btns.append([InlineKeyboardButton(text="⬅️ Назад к списку дней", callback_data="back_days")])
    await call.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("rec_"))
async def show_rec(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_"); data = await state.get_data()
    meal = data['plan'][int(parts[1])-1]['meals'][int(parts[2])]
    
    txt = (
        f"Готовим блюдо: {meal['name']}\n\n"
        "Тебе понадобятся следующие ингредиенты:\n"
    )
    txt += "\n".join([f"— {i['name']} ({i['quantity']})" for i in meal['ingredients']])
    txt += f"\n\nИнструкция по приготовлению:\n{meal['instructions']}"
    txt += f"\n\nЭто блюдо содержит {meal['calories']} калорий. Приятного аппетита! 👨‍🍳"
    
    await call.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к меню дня", callback_data=f"day_{parts[1]}")]]))

@dp.callback_query(F.data == "shop_7")
async def shop_7(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ingredients = aggregate_ingredients(data['plan'])
    
    txt = "Вот твой полный список покупок на 7 дней. Я уже объединил все продукты за тебя, чтобы было удобнее:\n\n"
    for name, info in ingredients.items():
        val = int(info['val']) if isinstance(info['val'], float) and info['val'].is_integer() else info['val']
        txt += f"— {name.capitalize()}: {val} {info['unit']}\n"
    
    txt += (
        "\n📢 Подписывайся на наш канал с лайфхаками: " + TG_CHANNEL + 
        "\n\n💎 А если хочешь попробовать магию ИИ (считать калории по фото, чат с диетологом и умные замены), "
        "переходи в нашу Плюс-версию: " + PLUS_BOT
    )
    await call.message.answer(txt)
    await call.answer()

@dp.callback_query(F.data == "back_days")
async def back_days(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
    btns.append([InlineKeyboardButton(text="🛒 Список продуктов на 7 дней", callback_data="shop_7")])
    await call.message.edit_text(f"Выбери день для просмотра меню (Твоя норма: {data['norma']} ккал):", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# --- ЗАПУСК ---
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), use_reloader=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
