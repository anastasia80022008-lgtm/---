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
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)

# Библиотеки для PDF
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

# --- НАСТРОЙКИ ---
TOKEN = "8585043014:AAFQsH6ESYByucOgXq07WttwnYW4Pp0Vh78"
FONT_PATH = "DejaVuSans.ttf"  # Убедись, что этот файл есть в папке!
TG_CHANNEL = "https://t.me/TasteMeter"
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
    vegan = State()
    activity = State()
    age = State()
    height = State()
    weight = State()
    allergies = State()

# --- ЛОГИКА РАСЧЕТОВ ---

def get_activity_coeff(text):
    if "Минимальная" in text: return 1.2
    if "Низкая" in text: return 1.375
    if "Средняя" in text: return 1.55
    if "Высокая" in text: return 1.725
    if "Экстремальная" in text: return 1.9
    return 1.2

def get_user_block(goal, activity_text):
    coeff = get_activity_coeff(activity_text)
    # Упрощенная логика маппинга блоков (А-И)
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
        "Мясо и рыба": ["курица", "индейка", "говядина", "лосось", "треска", "тунец", "креветки", "бекон", "фарш", "минтай", "свинина"],
        "Овощи и фрукты": ["огурец", "помидор", "кабачок", "брокколи", "шпинат", "яблоко", "банан", "апельсин", "авокадо", "морковь", "лук", "чеснок", "перец", "тыква", "батат", "черника", "малина"],
        "Бакалея и крупы": ["гречка", "рис", "булгур", "киноа", "макароны", "нут", "чечевица", "овсяные", "хлеб", "хлебцы", "мука", "мед", "орехи", "масло", "чиа", "паста", "фунчоза", "кус-кус", "изюм", "курага"],
        "Молочное и альтернативы": ["молоко", "творог", "сыр", "яйца", "яйцо", "тофу", "сметана", "кефир", "йогурт"]
    }

    for day in plan:
        for meal in day['meals']:
            for ing in meal['ingredients']:
                name = ing['name'].lower().strip()
                qty_str = str(ing['quantity']).lower().strip()
                
                cat_found = "Разное"
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

# --- PDF ГЕНЕРАЦИЯ ---

def create_pdf(shopping_list, user_id):
    filename = f"shopping_list_{user_id}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    try:
        pdfmetrics.registerFont(TTFont('Russian', FONT_PATH))
        c.setFont('Russian', 14)
    except:
        logging.error("Шрифт не найден! PDF будет с ошибками.")
    
    c.drawString(50, height - 50, "Ваш список покупок на 7 дней (Вкусомер)")
    c.setFont('Russian', 10)
    y = height - 80
    
    for cat, items in shopping_list.items():
        if y < 100: 
            c.showPage()
            y = height - 50
            c.setFont('Russian', 10)
            
        c.setFont('Russian', 12)
        c.drawString(50, y, f"--- {cat} ---")
        y -= 20
        c.setFont('Russian', 10)
        
        for name, info in items.items():
            val = info['val']
            # Логика Zero Waste (округление для магазина)
            advice = ""
            if info['unit'] == "г" and val > 500:
                advice = f" (Купите упаковку ~1кг)"
            elif info['unit'] == "г" and val <= 500:
                advice = f" (Хватит маленькой пачки)"
            elif "шт" in info['unit']:
                val = int(val + 0.9) # округление вверх до целого яйца/яблока
            
            display_val = int(val) if isinstance(val, float) and val.is_integer() else val
            c.drawString(70, y, f"- {name.capitalize()}: {display_val} {info['unit']}{advice}")
            y -= 15
            if y < 50: 
                c.showPage()
                y = height - 50
        y -= 10

    c.setFont('Russian', 10)
    y -= 20
    c.drawString(50, y, "🧂 Базовые продукты (проверьте наличие): соль, перец, вода, масло.")
    c.save()
    return filename

# --- ОБРАБОТЧИКИ ---

@app.route('/')
def index(): return "Бот работает"

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]], resize_keyboard=True)
    await message.answer("<b>Здравствуйте!</b> Приветствую в системе Вкусомер. Давайте создадим ваш идеальный рацион.\n\nУкажите ваш пол:", reply_markup=kb, parse_mode="HTML")
    await state.set_state(Survey.gender)

@dp.message(Survey.gender)
async def proc_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Похудеть"), KeyboardButton(text="Набрать массу"), KeyboardButton(text="Поддерживать вес")]], resize_keyboard=True)
    await message.answer("Ваша цель:", reply_markup=kb)
    await state.set_state(Survey.goal)

@dp.message(Survey.goal)
async def proc_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Да 🌱"), KeyboardButton(text="Нет 🍖")]], resize_keyboard=True)
    await message.answer("Вы придерживаетесь веганства?", reply_markup=kb)
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
    await message.answer("Выберите уровень вашей активности:", reply_markup=kb)
    await state.set_state(Survey.activity)

@dp.message(Survey.activity)
async def proc_act(message: types.Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.answer("Ваш возраст?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Survey.age)

@dp.message(Survey.age)
async def proc_age(message: types.Message, state: FSMContext):
    val = re.findall(r"\d+", message.text)
    if not val: return await message.answer("Введите число.")
    await state.update_data(age=int(val[0]))
    await message.answer("Ваш рост в см?")
    await state.set_state(Survey.height)

@dp.message(Survey.height)
async def proc_h(message: types.Message, state: FSMContext):
    val = re.findall(r"\d+", message.text)
    if not val: return await message.answer("Введите число.")
    await state.update_data(height=int(val[0]))
    await message.answer("Ваш вес в кг?")
    await state.set_state(Survey.weight)

@dp.message(Survey.weight)
async def proc_w(message: types.Message, state: FSMContext):
    val = re.findall(r"\d+", message.text)
    if not val: return await message.answer("Введите число.")
    await state.update_data(weight=int(val[0]))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Лактоза 🥛", callback_data="allg_lactose"), InlineKeyboardButton(text="Глютен 🍞", callback_data="allg_gluten")],
        [InlineKeyboardButton(text="Орехи 🥜", callback_data="allg_nuts"), InlineKeyboardButton(text="Морепродукты 🦐", callback_data="allg_seafood")],
        [InlineKeyboardButton(text="Я ем всё / Нет аллергий ✅", callback_data="allg_done")]
    ])
    await message.answer("Отметьте ваши ограничения или нажмите Готово:", reply_markup=kb)
    await state.update_data(user_allg=[])

@dp.callback_query(F.data.startswith("allg_"))
async def proc_allg(call: types.CallbackQuery, state: FSMContext):
    if call.data == "allg_done":
        data = await state.get_data()
        w, h, a, gen = data['weight'], data['height'], data['age'], data['gender']
        
        # Расчет по Миффлину
        bmr = (10 * w) + (6.25 * h) - (5 * a) + (5 if gen == "Мужской" else -161)
        norma = int(bmr * get_activity_coeff(data['activity']))
        if data['goal'] == "Похудеть": norma = int(norma * 0.85)
        if data['goal'] == "Набрать массу": norma = int(norma * 1.15)
        
        # Генерация плана
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
        
        btns = [[InlineKeyboardButton(text=f"День {i}", callback_data=f"day_{i}")] for i in range(1, 8)]
        btns.append([InlineKeyboardButton(text="🛒 Список покупок", callback_data="shop_view")])
        await call.message.edit_text(f"Ваш рацион на <b>{norma} ккал</b> готов! Выберите день:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="HTML")
    else:
        allg = call.data.replace("allg_", "")
        d = await state.get_data(); current = d['user_allg']
        if allg not in current: current.append(allg)
        await state.update_data(user_allg=current); await call.answer(f"Ограничение добавлено")

# --- ПРОСМОТР И ЗАМЕНА ---

@dp.callback_query(F.data.startswith("day_"))
async def show_day(call: types.CallbackQuery, state: FSMContext):
    day_num = int(call.data.split("_")[1]); data = await state.get_data(); day_meals = data['plan'][day_num-1]['meals']
    text = f"<b>📅 ДЕНЬ {day_num}</b>\nНорма: {data['norma']} ккал\n\n"
    btns = []
    for i, m in enumerate(day_meals):
        text += f"🍴 {m['name']} ({m['calories']} ккал)\n"
        btns.append([InlineKeyboardButton(text=f"Рецепт: {m['name']}", callback_data=f"view_{day_num}_{i}")])
    btns.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="allg_done")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="HTML")

@dp.callback_query(F.data.startswith("view_"))
async def view_recipe(call: types.CallbackQuery, state: FSMContext):
    _, d, m_idx = call.data.split("_"); data = await state.get_data()
    meal = data['plan'][int(d)-1]['meals'][int(m_idx)]
    res = f"<b>🍳 {meal['name']}</b>\n\n<b>Ингредиенты:</b>\n"
    res += "\n".join([f"— {i['name']}: {i['quantity']}" for i in meal['ingredients']])
    res += f"\n\n<b>Инструкция:</b>\n{meal['instructions']}"
    kb = [
        [InlineKeyboardButton(text="🔄 Заменить блюдо", callback_data=f"replace_{d}_{m_idx}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"day_{d}")]
    ]
    await call.message.edit_text(res, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("replace_"))
async def replace_meal(call: types.CallbackQuery, state: FSMContext):
    _, d, m_idx = call.data.split("_"); data = await state.get_data()
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
        await call.answer("Нет других вариантов в этом блоке", show_alert=True)

@dp.callback_query(F.data == "shop_view")
async def shop_view(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); shop_list = aggregate_shopping_list(data['plan'])
    text = "<b>🛒 Список покупок подготовлен!</b>\n\nВсе продукты объединены и округлены для удобной закупки в магазине. Вы можете скачать его в формате PDF."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать PDF", callback_data="shop_pdf")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="allg_done")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "shop_pdf")
async def shop_pdf(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); shop_list = aggregate_shopping_list(data['plan'])
    file_path = create_pdf(shop_list, call.from_user.id)
    await call.message.answer_document(FSInputFile(file_path), caption="Ваш список покупок!")
    os.remove(file_path) # Удаляем временный файл
    await call.answer()

# --- СЛУЖЕБНОЕ ---
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), use_reloader=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
