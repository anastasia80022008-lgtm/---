# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import json
import random
import re
import threading
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
TOKEN = "8585043014:AAFQsH6ESYByucOgXq07WttwnYW4Pp0Vh78"  # Замени на свой токен!
TG_CHANNEL = "https://t.me/TasteMeter"
PLUS_BOT = "https://t.me/TasteMeterPlus_bot"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- ЗАГРУЗКА РЕЦЕПТОВ ---
ALL_RECIPES = []
if os.path.exists('recipes.json'):
    try:
        with open('recipes.json', 'r', encoding='utf-8') as f:
            ALL_RECIPES = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки JSON: {e}")

# --- СОСТОЯНИЯ ---
class Survey(StatesGroup):
    gender = State()
    goal = State()
    vegan = State()
    activity = State()
    age = State()
    height = State()
    weight = State()
    allergies = State()

# --- ЛОГИКА ---

def get_activity_coeff(text):
    if "1." in text: return 1.2
    if "2." in text: return 1.375
    if "3." in text: return 1.55
    if "4." in text: return 1.725
    if "5." in text: return 1.9
    return 1.2

def get_user_block(goal, activity_text):
    coeff = get_activity_coeff(activity_text)
    act_level = "низкая" if coeff <= 1.375 else "средняя" if coeff <= 1.55 else "высокая"
    mapping = {
        ("Похудеть", "низкая"): "А", ("Похудеть", "средняя"): "Б", ("Похудеть", "высокая"): "В",
        ("Поддерживать вес", "низкая"): "Г", ("Поддерживать вес", "средняя"): "Д", ("Поддерживать вес", "высокая"): "Е",
        ("Набрать массу", "низкая"): "Ж", ("Набрать массу", "средняя"): "З", ("Набрать массу", "высокая"): "И"
    }
    return mapping.get((goal, act_level), "А")

def aggregate_shopping_list(plan):
    shopping_list = {}
    categories = {
        "🥩 Мясо и рыба": ["курица", "индейка", "говядина", "лосось", "треска", "тунец", "креветки", "бекон", "фарш", "минтай", "свинина"],
        "🥦 Овощи и фрукты": ["огурец", "помидор", "кабачок", "брокколи", "шпинат", "яблоко", "банан", "апельсин", "авокадо", "морковь", "лук", "чеснок", "перец", "тыква", "батат", "черника", "малина"],
        "🥐 Бакалея и крупы": ["гречка", "рис", "булгур", "киноа", "макароны", "нут", "чечевица", "овсяные", "хлеб", "хлебцы", "мука", "мед", "орехи", "масло", "чиа", "паста", "фунчоза", "кус-кус", "изюм", "курага"],
        "🥛 Молочное и яйца": ["молоко", "творог", "сыр", "яйца", "яйцо", "тофу", "сметана", "кефир", "йогурт"]
    }

    for day in plan:
        for meal in day['meals']:
            for ing in meal['ingredients']:
                name = ing['name'].lower().strip()
                qty_str = str(ing['quantity']).lower().strip()
                
                cat_found = "📦 Разное"
                for cat, keywords in categories.items():
                    if any(word in name for word in keywords):
                        cat_found = cat
                        break
                
                if cat_found not in shopping_list: shopping_list[cat_found] = {}
                
                match = re.search(r"(\d+[\.,]?\d*)", qty_str)
                unit = re.sub(r"(\d+[\.,]?\d*)", "", qty_str).strip()
                
                if match:
                    val = float(match.group(1).replace(",", "."))
                    if name not in shopping_list[cat_found]:
                        shopping_list[cat_found][name] = {"val": val, "unit": unit}
                    else:
                        if shopping_list[cat_found][name]["unit"] == unit:
                            shopping_list[cat_found][name]["val"] += val
                else:
                    shopping_list[cat_found][name] = {"val": qty_str, "unit": ""}
    return shopping_list

# --- ОБРАБОТЧИКИ ---

@app.route('/')
def index(): return "Бот Вкусомер активен!"

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    welcome = (
        "<b>Здравствуйте! Приветствую вас в системе Вкусомер.</b> 🥗\n\n"
        "Я ваш персональный диетолог. Я рассчитаю вашу норму калорий и составлю меню на 7 дней без повторов.\n\n"
        "Давайте начнем! Ваш пол? 👤"
    )
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
    await message.answer(welcome, reply_markup=kb, parse_mode="HTML")
    await state.set_state(Survey.gender)

@dp.message(Survey.gender)
async def proc_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Набрать массу"), KeyboardButton(text="Поддерживать вес")]], resize_keyboard=True)
    await message.answer("Принято. Какая у вас главная цель? 🎯", reply_markup=kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal)
async def proc_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Да, я веган 🌱"), KeyboardButton(text="Нет, ем всё 🍖")]], resize_keyboard=True)
    await message.answer("Придерживаетесь ли вы веганства?", reply_markup=kb)
    await state.set_state(Survey.vegan)

@dp.message(Survey.vegan)
async def proc_vegan(message: types.Message, state: FSMContext):
    await state.update_data(vegan=True if "Да" in message.text else False)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="1. Минимальная (Сидячий образ)")],
        [KeyboardButton(text="2. Низкая (1-3 тренировки в неделю)")],
        [KeyboardButton(text="3. Средняя (3-5 тренировок в неделю)")],
        [KeyboardButton(text="4. Высокая (6-7 тренировок в неделю)")],
        [KeyboardButton(text="5. Экстремальная (2 тренировки в день)")],
    ], resize_keyboard=True)
    await message.answer("Выберите уровень вашей физической активности:", reply_markup=kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity)
async def proc_act(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("Укажите ваш возраст:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def proc_age(message: types.Message, state: FSMContext):
    val = re.findall(r"\d+", message.text)
    if not val: return await message.answer("Пожалуйста, введите возраст числом.")
    await state.update_data(age=int(val[0]))
    await message.answer("Напишите ваш рост в см:")
    await state.set_state(Survey.height)

@dp.message(Survey.height)
async def proc_h(message: types.Message, state: FSMContext):
    val = re.findall(r"\d+", message.text)
    if not val: return await message.answer("Пожалуйста, введите рост числом.")
    await state.update_data(height=int(val[0]))
    await message.answer("Ваш текущий вес в кг?")
    await state.set_state(Survey.weight)

@dp.message(Survey.weight)
async def proc_w(message: types.Message, state: FSMContext):
    val = re.findall(r"\d+", message.text)
    if not val: return await message.answer("Пожалуйста, введите вес числом.")
    await state.update_data(weight=int(val[0]))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Лактоза 🥛", callback_data="allg_lactose"), InlineKeyboardButton(text="Глютен 🍞", callback_data="allg_gluten")],
        [InlineKeyboardButton(text="Орехи 🥜", callback_data="allg_nuts"), InlineKeyboardButton(text="Морепродукты 🦐", callback_data="allg_seafood")],
        [InlineKeyboardButton(text="Нет аллергий / Готово ✅", callback_data="allg_done")]
    ])
    await message.answer("Есть ли у вас пищевые аллергии?", reply_markup=kb)
    await state.update_data(user_allg=[])

@dp.callback_query(F.data.startswith("allg_"))
async def proc_allg(call: types.CallbackQuery, state: FSMContext):
    if call.data == "allg_done":
        data = await state.get_data()
        w, h, a, gen = data['weight'], data['height'], data['age'], data['gender']
        
        # РАСЧЕТ КАЛОРИЙ (Миффлин-Сан Жеор)
        bmr = (10 * w) + (6.25 * h) - (5 * a) + (5 if gen == "Мужской" else -161)
        coeff = get_activity_coeff(data['activity'])
        norma = int(bmr * coeff)
        
        if data['goal'] == "Похудеть": norma = int(norma * 0.85)
        if data['goal'] == "Набрать массу": norma = int(norma * 1.15)
        
        # ГЕНЕРАЦИЯ ПЛАНА
        block = get_user_block(data['goal'], data['activity'])
        suitable = [r for r in ALL_RECIPES if block in r['blocks'] and (not data['vegan'] or r.get('is_vegan'))]
        suitable = [r for r in suitable if not any(al in r.get('allergens', []) for al in data['user_allg'])]
        
        if len(suitable) < 5: suitable = ALL_RECIPES
        
        br = [r for r in suitable if r['meal_type'] == 'breakfast']
        lu = [r for r in suitable if r['meal_type'] == 'lunch']
        di = [r for r in suitable if r['meal_type'] == 'dinner']
        
        plan = []
        for i in range(1, 8):
            plan.append({"day": i, "meals": [random.choice(br), random.choice(lu), random.choice(di)]})
        
        await state.update_data(plan=plan, norma=norma)
        
        res_text = (
            f"<b>Ваш профиль готов!</b> ✅\n\n"
            f"Ваша индивидуальная норма: <b>{norma} ккал</b> в день.\n"
            f"Я подобрал для вас оптимальное меню на 7 дней. Выберите день, чтобы увидеть рецепты:"
        )
        btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
        btns.append([InlineKeyboardButton(text="🛒 Список покупок на неделю", callback_data="shop_view")])
        await call.message.edit_text(res_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="HTML")
    else:
        allg = call.data.replace("allg_", "")
        d = await state.get_data(); current = d['user_allg']
        if allg not in current: current.append(allg)
        await state.update_data(user_allg=current); await call.answer(f"Добавлено ограничение")

# --- МЕНЮ ПРОСМОТРА ---

@dp.callback_query(F.data.startswith("day_"))
async def show_day(call: types.CallbackQuery, state: FSMContext):
    day_num = int(call.data.split("_")[1])
    data = await state.get_data()
    day_meals = data['plan'][day_num-1]['meals']
    
    text = f"<b>📅 МЕНЮ НА ДЕНЬ {day_num}</b>\nЦель: {data['norma']} ккал\n\n"
    btns = []
    for i, m in enumerate(day_meals):
        text += f"🍴 {m['name']} ({m['calories']} ккал)\n"
        btns.append([InlineKeyboardButton(text=f"Рецепт: {m['name']}", callback_data=f"view_{day_num}_{i}")])
    
    btns.append([InlineKeyboardButton(text="⬅️ Назад к выбору дней", callback_data="allg_done")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="HTML")

@dp.callback_query(F.data.startswith("view_"))
async def view_recipe(call: types.CallbackQuery, state: FSMContext):
    _, d, m_idx = call.data.split("_")
    data = await state.get_data()
    meal = data['plan'][int(d)-1]['meals'][int(m_idx)]
    
    res = f"<b>🍳 {meal['name']}</b>\n\n<b>Ингредиенты:</b>\n"
    res += "\n".join([f"— {i['name']}: {i['quantity']}" for i in meal['ingredients']])
    res += f"\n\n<b>Инструкция:</b>\n{meal['instructions']}"
    
    kb = [
        [InlineKeyboardButton(text="🔄 Заменить это блюдо", callback_data=f"replace_{d}_{m_idx}")],
        [InlineKeyboardButton(text="⬅️ Назад к меню дня", callback_data=f"day_{d}")]
    ]
    await call.message.edit_text(res, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("replace_"))
async def replace_meal(call: types.CallbackQuery, state: FSMContext):
    _, d, m_idx = call.data.split("_")
    data = await state.get_data()
    m_idx = int(m_idx); d_idx = int(d)-1
    curr = data['plan'][d_idx]['meals'][m_idx]
    
    block = get_user_block(data['goal'], data['activity'])
    options = [r for r in ALL_RECIPES if r['meal_type'] == curr['meal_type'] and block in r['blocks'] and r['id'] != curr['id']]
    if data['vegan']: options = [r for r in options if r.get('is_vegan')]
    
    if options:
        data['plan'][d_idx]['meals'][m_idx] = random.choice(options)
        await state.update_data(plan=data['plan'])
        await call.answer("Блюдо заменено!")
        await view_recipe(call, state)
    else:
        await call.answer("Других вариантов в этом блоке пока нет", show_alert=True)

@dp.callback_query(F.data == "shop_view")
async def shop_view(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    shop_list = aggregate_shopping_list(data['plan'])
    
    msg = "<b>🛒 ВАШ СПИСОК ПОКУПОК НА 7 ДНЕЙ</b>\n\n"
    for cat, items in shop_list.items():
        msg += f"<b>{cat}:</b>\n"
        for name, info in items.items():
            val = info['val']
            # Zero Waste логика (советы)
            advice = ""
            if info['unit'] == "г" and val > 500: advice = " 📦 <i>(купите 1 пачку)</i>"
            elif "шт" in info['unit']: val = int(val + 0.9) # округление яиц
            
            display_val = int(val) if isinstance(val, float) and val.is_integer() else val
            msg += f" • {name.capitalize()}: {display_val} {info['unit']}{advice}\n"
        msg += "\n"
    
    msg += "🧂 <b>Базовые продукты (проверьте дома):</b>\nсоль, перец, вода, растительное масло, специи.\n\n"
    msg += f"📢 Наш канал: {TG_CHANNEL}\n💎 Плюс-версия с ИИ: {PLUS_BOT}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к меню", callback_data="allg_done")]])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")

# --- ЗАПУСК ---
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), use_reloader=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
