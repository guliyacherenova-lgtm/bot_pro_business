# -*- coding: utf-8 -*-
import asyncio
import logging
import json
import aiohttp
import ssl
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, GIGACHAT_CLIENT_ID, GIGACHAT_CLIENT_SECRET, REF_LINK

PHOTO_1 = Path(__file__).parent / "photo.jpg"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_gigachat_token = None
_token_expires_at = 0

async def get_gigachat_token():
    global _gigachat_token, _token_expires_at
    import time, uuid
    if _gigachat_token and time.time() < _token_expires_at:
        return _gigachat_token
    if not GIGACHAT_CLIENT_ID or not GIGACHAT_CLIENT_SECRET:
        return None
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json", "RqUID": str(uuid.uuid4()), "Authorization": f"Basic {GIGACHAT_CLIENT_SECRET}"}
            async with session.post("https://ngw.devices.sberbank.ru:9443/api/v2/oauth", headers=headers, data={"scope": "GIGACHAT_API_PERS"}, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    result = await response.json()
                    _gigachat_token = result.get("access_token")
                    _token_expires_at = time.time() + result.get("expires_at", 1800) - 300
                    return _gigachat_token
    except Exception as e:
        logger.error(f"Token error: {e}")
    return None

async def extract_user_info(text: str) -> dict:
    """Извлекает город, деятельность, хобби и мотивацию из текста пользователя через GigaChat."""
    if not GIGACHAT_CLIENT_ID or not GIGACHAT_CLIENT_SECRET:
        logger.info("GigaChat не настроен, использую fallback обработку")
        return extract_user_info_fallback(text)
    
    token = await get_gigachat_token()
    if not token:
        return extract_user_info_fallback(text)
    
    prompt = f"""Проанализируй текст пользователя и извлеки информацию.

Текст пользователя: "{text}"

Правила извлечения:
1. Город - выбери ОДИН город проживания. Если несколько - выбери основной.
2. Деятельность - перечисли ВСЕ профессии и занятия через запятую (например: "ветеринар, финансист, программист")
3. Хобби - перечисли все увлечения через запятую (например: "сноуборд, чтение, путешествия")
4. Мотивация - извлеки ключевые слова через запятую: доход, развитие, поддержка, комьюнити, накопления, свобода, независимость и т.д.

Верни ответ ТОЛЬКО в формате JSON без markdown:
{{"city": "город", "profession": "профессия1, профессия2", "hobby": "хобби1, хобби2", "motivation": "ключевое1, ключевое2"}}

Если что-то не указано, оставь пустую строку."""

    try:
        answer = await ask_gigachat(prompt, is_json=True, token=token)
        
        # Парсим JSON из ответа
        answer = answer.strip()
        if answer.startswith("```json"):
            answer = answer[7:]
        if answer.startswith("```"):
            answer = answer[3:]
        if answer.endswith("```"):
            answer = answer[:-3]
        answer = answer.strip()
        
        info = json.loads(answer)
        logger.info(f"GigaChat извлёк: {info}")
        return info
                    
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON от GigaChat: {e}")
        return extract_user_info_fallback(text)
    except Exception as e:
        logger.error(f"Ошибка при обращении к GigaChat: {e}")
        return extract_user_info_fallback(text)

async def ask_gigachat(question, user_data=None, is_json=False, token=None, chat_history=None):
    """Отправляет вопрос в GigaChat и возвращает ответ. Поддерживает историю диалога."""
    if not token:
        token = await get_gigachat_token()
    if not token:
        return "⚠️ GigaChat не настроен."
    
    # Извлекаем данные пользователя
    name = "Друг"
    style = "ty"
    age = ""
    city = ""
    goal = ""
    if user_data:
        n = user_data.get("name")
        name = n.title() if n else "Друг"
        style = user_data.get("style", "ty")
        age = user_data.get("age", "")
        city = user_data.get("city", "")
        goal = user_data.get("motivation", "")
    
    if is_json:
        system_prompt = "Return only JSON."
    else:
        # Определяем, первое ли это сообщение (нет истории)
        is_first_message = not chat_history or len(chat_history) == 0
        
{"text": "        system_prompt = f\"\"\"Ты — профессиональный бизнес-консультант и наставник в сфере реферального бизнеса.\r\nТвоя задача — вести кандидата дружелюбно, мотивировать и помогать разобраться в возможностях реферального бизнеса.\r\n\r\nПравила поведения:\r\n1. Всегда обращайся по имени пользователя {name}.\r\n2. {\"Приветствие — только ОДИН РАЗ в самом начале диалога. Сейчас диалог уже идёт — НЕ здоровайся снова!\" if not is_first_message else \"Приветствуй пользователя один раз в начале.\"}\r\n3. Тема диалога ограничена: реферальный бизнес, продукция, мотивация, навыки и развитие.\r\n4. Любые посторонние вопросы игнорируй и мягко возвращай к бизнес-теме.\r\n5. Используй данные анкеты: возраст {age}, город {city}, мотивация {goal}, стиль общения {style}.\r\n6. Если пользователь ХОЧЕТ зарегистрироваться — дай ссылку: {REF_LINK}\r\n7. Отвечай коротко — 2–4 предложения. С эмодзи.\r\n8. Не обещай быстрых миллионов.\r\n\r\nВАЖНО - ОБРАБОТКА ВОЗРАЖЕНИЙ:\r\nЕсли пользователь выражает сомнения или негатив (\"пирамида\", \"обман\", \"не моё\", \"нет денег\"):\r\n- НЕ давай ссылку на регистрацию!\r\n- Спокойно ответь на возражение, назови преимущества реферального бизнеса\r\n- Спроси, есть ли ещё вопросы\r\n- Только после позитивного отклика предлагай следующий шаг\r\n\r\nПримеры ответов:\r\n- На \"пирамида\": \"{name}, финансовая пирамида — когда нет продукта. В реферальном бизнесе — качественная продукция для здоровья. Можно просто пользоваться со скидкой или строить бизнес.\"\r\n- На \"нет денег\": \"Понимаю, {name}. Начать можно с минимального заказа. Главное — желание и поддержка команды.\"\r\n\r\nРегистрационная ссылка: {REF_LINK}\r\nОтвечай на русском языке.\"\"\""}
    
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Формируем сообщения с историей
        messages = [{"role": "system", "content": system_prompt}]
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": question})
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            data = {
                "model": "GigaChat",
                "messages": messages,
                "temperature": 0.3 if is_json else 0.7,
                "max_tokens": 200 if is_json else 500
            }
            async with session.post(
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    return (await response.json()).get("choices", [{}])[0].get("message", {}).get("content", "")
                return f"Error {response.status}"
    except Exception as e:
        return f"Error: {e}"

class UserStates(StatesGroup):
    main = State()
    ai_chat = State()

class QualificationStates(StatesGroup):
    gender = State()
    name = State()
    style = State()
    age = State()
    info = State()
    motivation = State()
    custom_motivation = State()
    block2 = State()

bot = Bot(token=BOT_TOKEN, request_timeout=120, connect_timeout=120)
dp = Dispatcher(storage=MemoryStorage())

BTN_START = "🚀 Начать"
BTN_STORY = "💼 История наставника"
BTN_PROFILE = "📝 Моя анкета"
BTN_REG = "🎯 Регистрация"
BTN_ASK = "🙋‍♂️ Задать вопрос"

def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=BTN_START)],
        [KeyboardButton(text=BTN_STORY)],
        [KeyboardButton(text=BTN_PROFILE)],
        [KeyboardButton(text=BTN_REG)],
        [KeyboardButton(text=BTN_ASK)]], resize_keyboard=True)

def get_limited_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_START)]], resize_keyboard=True)

def get_block2_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📺 О компании (2 мин)")],
        [KeyboardButton(text="🥗 О продукте за 60 сек")],
        [KeyboardButton(text="❓ У меня есть вопросы")],
        [KeyboardButton(text="🚀 Готов(а) регистрироваться!")]], resize_keyboard=True)

def get_style_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="На «ты» 👊")],
        [KeyboardButton(text="На «Вы» 🤝")]], resize_keyboard=True)

def get_motivation_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Доход")],
        [KeyboardButton(text="📈 Саморазвитие")],
        [KeyboardButton(text="🥳 Тусовки и общение")],
        [KeyboardButton(text="🏝️ Свобода/Независимость")],
        [KeyboardButton(text="✍️ Свой вариант")]], resize_keyboard=True)

def get_gender_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👨 Мужчина")],
        [KeyboardButton(text="👩 Женщина")]], resize_keyboard=True)

@dp.message(F.text == BTN_START)
async def btn_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QualificationStates.gender)
    await message.answer("👋 <b>Привет!</b>\n\nЯ твой проводник в мир бизнеса с NL. Помогу разобраться, подходит ли тебе эта модель, за 2 минуты.\n\n<b>Ты мужчина или женщина?</b>", parse_mode="HTML", reply_markup=get_gender_keyboard())

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QualificationStates.gender)
    await message.answer("👋 <b>Привет!</b>\n\nЯ твой проводник в мир бизнеса с NL. Помогу разобраться, подходит ли тебе эта модель, за 2 минуты.\n\n<b>Ты мужчина или женщина?</b>", parse_mode="HTML", reply_markup=get_gender_keyboard())

@dp.message(F.text == BTN_STORY)
async def btn_my_story(message: types.Message, state: FSMContext):
    data = await state.get_data()
    age = data.get("age", 0)
    keyboard = get_main_keyboard() if age >= 14 else get_limited_keyboard()
    story = "🚀 <b>История старта</b>\n\n<b>Счастье быть рядом и свобода быть собой</b>\n\nКогда я уходила в декрет, я думала, что это будет время покоя. Но мамы поймут: мир сузился до границ детской площадки.\n\nЯ хотела дать ребёнку всё лучшее, но не хотела пропадать на работе. Мне была важна независимость — финансовая и внутренняя.\n\nПоэтому я пришла в реферальный бизнес NL. Мой офис — в смартфоне. Я строю бизнес, пока малыш спит. NL — это свобода без жертв. ✨"
    try:
        if PHOTO_1.exists():
            await bot.send_photo(chat_id=message.chat.id, photo=FSInputFile(PHOTO_1))
    except:
        pass
    await message.answer(story, parse_mode="HTML", reply_markup=keyboard)

@dp.message(F.text == BTN_REG)
async def btn_registration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_data = data.get("user_data", {})
    name = user_data.get("name", "")
    style = user_data.get("style", "ty")
    age = data.get("age", 0)
    keyboard = get_main_keyboard() if age >= 14 else get_limited_keyboard()
    ref_link = REF_LINK
    if name:
        name = name.title()
    # Обращение на "ты" или "вы"
    if style == "ty":
        msg = f"🚀 <b>Регистрация</b>\n\n{name}, я буду рядом на каждом шаге.\nРегистрируйся, и я покажу, как быстро освоить систему:\n\n👉 <a href=\"{ref_link}\">Зарегистрироваться</a>\n\n📤 Поделись ссылкой с друзьями!"
    else:
        msg = f"🚀 <b>Регистрация</b>\n\n{name}, я буду рядом на каждом шаге.\nРегистрируйтесь, и я покажу, как быстро освоить систему:\n\n👉 <a href=\"{ref_link}\">Зарегистрироваться</a>\n\n📤 Поделитесь ссылкой с друзьями!"
    await message.answer(msg, parse_mode="HTML", reply_markup=keyboard)

@dp.message(F.text == BTN_PROFILE)
async def btn_my_profile(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_data = data.get("user_data")
    age = data.get("age", 0)
    keyboard = get_main_keyboard() if age >= 14 else get_limited_keyboard()
    if not user_data:
        await message.answer("📝 Ты ещё не заполнил анкету. Нажми /start!", reply_markup=keyboard)
        return
    name = user_data.get("name", "").title()
    gender = user_data.get("gender", "male")
    user_age = user_data.get("age", 0)
    city = user_data.get("city", "").title()
    profession = user_data.get("profession", "")
    hobby = user_data.get("hobby", "")
    motivation = user_data.get("motivation", "")
    gender_text = "Мужчина" if gender == "male" else "Женщина"
    hobby_line = f"🎨 Хобби: {hobby}\n" if hobby else ""
    gender_emoji = "👨" if gender == "male" else "👩"
    # Обращение на "ты" или "вы"
    if style == "ty":
        intro = f"🎉 <b>Отлично, {name}!</b>\nЯ записала твои ответы:\n"
    else:
        intro = f"🎉 <b>Отлично, {name}!</b>\nЯ записала ваши ответы:\n"
    await message.answer(f"{intro}👤 Имя: {name}\n{gender_emoji} Пол: {gender_text}\n🎂 Возраст: {user_age}\n📍 Город: {city}\n{hobby_line}💼 Деятельность: {profession}\n🎯 Мотивация: {motivation}\n\nТеперь я могу предложить {'тебе' if style == 'ty' else 'вам'} подходящий вариант сотрудничества!", parse_mode="HTML", reply_markup=keyboard)

@dp.message(F.text == BTN_ASK)
async def btn_ask_question(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.ai_chat)
    await message.answer("🙋‍♀️ Задай любой вопрос — я помогу.\n\n💡 Для выхода /cancel", parse_mode="HTML")

@dp.message(StateFilter(QualificationStates.gender))
async def qual_gender(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    if "мужчина" in text or "парень" in text:
        gender = "male"
    elif "женщина" in text or "девушка" in text:
        gender = "female"
    else:
        await message.answer("Выбери вариант кнопкой.")
        return
    await state.update_data(gender=gender)
    await state.set_state(QualificationStates.name)
    await message.answer("Как тебя зовут?")

@dp.message(StateFilter(QualificationStates.name))
async def qual_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("Имя от 2 до 50 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(QualificationStates.style)
    await message.answer(f"Приятно познакомиться, {name.title()}! Как нам удобнее общаться?", reply_markup=get_style_keyboard())

@dp.message(StateFilter(QualificationStates.style))
async def qual_style(message: types.Message, state: FSMContext):
    text = message.text
    if "ты" in text.lower():
        style = "ty"
    elif "вы" in text.lower():
        style = "Vy"
    else:
        await message.answer("Выбери вариант кнопкой.")
        return
    await state.update_data(style=style)
    data = await state.get_data()
    name = data.get("name", "Friend").title()
    await state.set_state(QualificationStates.age)
    if style == "ty":
        await message.answer(f"Договорились, {name}! Сколько тебе лет?")
    else:
        await message.answer(f"Принято, {name}! Сколько вам лет?")

@dp.message(StateFilter(QualificationStates.age))
async def qual_age(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Напиши возраст числом.")
        return
    age = int(text)
    await state.update_data(age=age)
    data = await state.get_data()
    name = data.get("name", "Friend").title()
    style = data.get("style", "ty")
    if age < 14:
        await state.clear()
        await state.set_state(UserStates.main)
        await message.answer(f"{name}, ты большой молодец, что уже в таком возрасте интересуешься созданием своего дела! Это настоящий характер лидера. 🚀\n\nНо регистрация в NL возможна только с 14 лет (с паспортом).\n\n📌 Сохрани этот бот и возвращайся, когда исполнится 14! Я буду тебя ждать!", reply_markup=get_limited_keyboard())
        return
    await state.set_state(QualificationStates.info)
    if style == "ty":
        await message.answer(f"Отлично, {name}! Расскажи о себе: из какого ты города, чем занимаешься и какие у тебя увлечения?")
    else:
        await message.answer(f"Благодарю за ответ, {name}. Расскажите о себе: из какого вы города, чем занимаетесь и какие у вас увлечения?")

@dp.message(StateFilter(QualificationStates.info))
async def qual_info(message: types.Message, state: FSMContext):
    user_text = message.text.strip()
    if len(user_text) < 3:
        await message.answer("Напиши подробнее.")
        return
    await message.answer("Обрабатываю... ⏳")
    info = await extract_user_info(user_text)
    await state.update_data(city=info.get("city", ""), profession=info.get("profession", ""), hobby=info.get("hobby", ""))
    extracted_motivation = info.get("motivation", "")
    if extracted_motivation:
        await state.update_data(motivation=extracted_motivation)
        await finish_qualification(message, state, extracted_motivation)
    else:
        data = await state.get_data()
        style = data.get("style", "ty")
        await state.set_state(QualificationStates.motivation)
        if style == "ty":
            await message.answer("И последнее, что для тебя важнее всего в работе сейчас?", reply_markup=get_motivation_keyboard())
        else:
            await message.answer("И последнее, что для вас важнее всего в работе сейчас?", reply_markup=get_motivation_keyboard())

@dp.message(StateFilter(QualificationStates.motivation))
async def qual_motivation(message: types.Message, state: FSMContext):
    motivation = message.text.strip()
    if "свой вариант" in motivation.lower():
        await state.set_state(QualificationStates.custom_motivation)
        await message.answer("✍️ Напиши свой вариант:")
        return
    await finish_qualification(message, state, motivation)

@dp.message(StateFilter(QualificationStates.custom_motivation))
async def qual_custom_motivation(message: types.Message, state: FSMContext):
    motivation = message.text.strip()
    if len(motivation) < 3:
        await message.answer("Напиши подробнее.")
        return
    await finish_qualification(message, state, motivation)

async def finish_qualification(message: types.Message, state: FSMContext, motivation: str):
    await state.update_data(motivation=motivation)
    data = await state.get_data()
    name = data.get("name", "Friend").title()
    style = data.get("style", "ty")
    gender = data.get("gender", "male")
    age = data.get("age", 0)
    city = data.get("city", "").title()
    profession = data.get("profession", "")
    hobby = data.get("hobby", "")
    user_data = {"name": data.get("name", ""), "style": style, "gender": gender, "age": age, "city": city, "profession": profession, "hobby": hobby, "motivation": motivation}
    await state.update_data(user_data=user_data)
    gender_text = "Мужчина" if gender == "male" else "Женщина"
    hobby_line = f"🎨 Хобби: {hobby}\n" if hobby else ""
    gender_emoji = "👨" if gender == "male" else "👩"
    # Обращение на "ты" или "вы"
    if style == "ty":
        intro = f"🎉 <b>Отлично, {name}!</b>\nЯ записала твои ответы:\n"
    else:
        intro = f"🎉 <b>Отлично, {name}!</b>\nЯ записала ваши ответы:\n"
    await message.answer(f"{intro}👤 Имя: {name}\n{gender_emoji} Пол: {gender_text}\n🎂 Возраст: {age}\n📍 Город: {city}\n{hobby_line}💼 Деятельность: {profession}\n🎯 Мотивация: {motivation}\n\nТеперь я могу предложить {'тебе' if style == 'ty' else 'вам'} подходящий вариант сотрудничества!", parse_mode="HTML")
    await state.set_state(QualificationStates.block2)
    if style == "ty":
        if gender == "male":
            question = f"{name}, спасибо, что поделился! Ты готов поработать на результат?"
        else:
            question = f"{name}, спасибо, что поделилась! Ты готова поработать на результат?"
    else:
        question = f"{name}, благодарю за ответы! Вы готовы рассмотреть этот бизнес серьёзно?"
    await message.answer(question, parse_mode="HTML", reply_markup=get_block2_keyboard())

@dp.message(StateFilter(QualificationStates.block2))
async def block2_handler(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    data = await state.get_data()
    user_data = data.get("user_data", {})
    name = user_data.get("name", "Friend").title()
    style = user_data.get("style", "ty")
    gender = user_data.get("gender", "male")
    age = data.get("age", 0)
    keyboard = get_main_keyboard() if age >= 14 else get_limited_keyboard()
    ref_link = REF_LINK
    if "регистриров" in text:
        await state.clear()
        await state.set_state(UserStates.main)
        await message.answer(f"🚀 Регистрация\n\n{name}, ссылка:\n\n👉 {ref_link}", parse_mode="HTML", reply_markup=keyboard)
        return
    if "о компании" in text or "2 мин" in text:
        await state.clear()
        await state.set_state(UserStates.main)
        await message.answer(f"📺 О компании\n\n{name}, видео (2 мин): https://youtube.com/watch?v=example", parse_mode="HTML", reply_markup=keyboard)
        return
    if "о продукте" in text or "60 сек" in text:
        await state.clear()
        await state.set_state(UserStates.main)
        await message.answer(f"🥗 О продукте\n\n{name}, видео (60 сек): https://youtube.com/watch?v=example2", parse_mode="HTML", reply_markup=keyboard)
        return
    if "есть вопросы" in text or "вопросы" in text:
        await state.clear()
        await state.set_state(UserStates.ai_chat)
        await message.answer(f"❓ {name}, задавай вопросы!" if style == "ty" else f"❓ {name}, задавайте вопросы!", parse_mode="HTML")
        return
    positive = ["да", "конечно", "ага", "yes", "yep", "точно"]
    if any(a in text for a in positive):
        msg = f"Отлично, {name}! Рад, что ты настроен серьёзно!\n\nЧто хочешь узнать?" if gender == "male" else f"Отлично, {name}! Рада, что ты настроена серьёзно!\n\nЧто хочешь узнать?"
        await message.answer(msg, reply_markup=get_block2_keyboard())
        return
    negative = ["нет", "неа", "no", "сомневаюсь"]
    if any(a in text for a in negative):
        await state.set_state(UserStates.ai_chat)
        await message.answer(f"{name}, что тебя смущает? Может помогу!" if style == "ty" else f"{name}, что вас смущает? Может помогу!")
        return
    await state.clear()
    await state.set_state(UserStates.main)
    await message.answer(f"Отлично, {name}! Выбери действие:", reply_markup=keyboard)

@dp.message(StateFilter(UserStates.ai_chat))
async def ai_chat_handler(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    data = await state.get_data()
    age = data.get("age", 0)
    user_data = data.get("user_data", {})
    if not user_data:
        user_data = {"name": data.get("name"), "style": data.get("style", "ty"), "age": data.get("age"), "city": data.get("city"), "motivation": data.get("motivation")}
    name = user_data.get("name", "Friend")
    name = name.title() if name else "Friend"
    style = user_data.get("style", "ty")
    keyboard = get_main_keyboard() if age >= 14 else get_limited_keyboard()
    ref_link = REF_LINK
    if any(kw in text for kw in ["регистрац", "готов", "хочу ссылку", "давай ссылку", "ссылку", "зарег", "хочу рег"]):
        await state.clear()
        await state.set_state(UserStates.main)
        # Обращение на "ты" или "вы"
        if style == "ty":
            reg_msg = f"🚀 <b>Регистрация</b>\n\n{name}, я буду рядом на каждом шаге.\nРегистрируйся, и я покажу, как быстро освоить систему:\n\n👉 <a href=\"{ref_link}\">Зарегистрироваться</a>\n\n📤 Поделись ссылкой с друзьями!"
        else:
            reg_msg = f"🚀 <b>Регистрация</b>\n\n{name}, я буду рядом на каждом шаге.\nРегистрируйтесь, и я покажу, как быстро освоить систему:\n\n👉 <a href=\"{ref_link}\">Зарегистрироваться</a>\n\n📤 Поделитесь ссылкой с друзьями!"
        await message.answer(reg_msg, parse_mode="HTML", reply_markup=keyboard)
        return
    if "о компании" in text or "2 мин" in text:
        await state.clear()
        await state.set_state(UserStates.main)
        await message.answer(f"📺 {name}, видео о NL (2 мин): https://youtube.com/watch?v=example", parse_mode="HTML", reply_markup=keyboard)
        return
    if "о продукте" in text or "60 сек" in text:
        await state.clear()
        await state.set_state(UserStates.main)
        await message.answer(f"🥗 {name}, видео о продукции (60 сек): https://youtube.com/watch?v=example2", parse_mode="HTML", reply_markup=keyboard)
        return
    
    
    # Получаем историю диалога
    chat_history = data.get("chat_history", [])
    
    answer = await ask_gigachat(message.text, user_data, chat_history=chat_history)
    if answer.startswith("Error"):
        answer += "\n\nПопробуй по-другому!"
    
    # Сохраняем историю (последние 10 сообщений = 5 пар вопрос-ответ)
    chat_history.append({"role": "user", "content": message.text})
    chat_history.append({"role": "assistant", "content": answer})
    if len(chat_history) > 10:
        chat_history = chat_history[-10:]
    await state.update_data(chat_history=chat_history)
    
    await message.answer(answer, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    age = data.get("age", 0)
    keyboard = get_main_keyboard() if age >= 14 else get_limited_keyboard()
    if current_state is None:
        await message.answer("❌ Нет активного режима.", reply_markup=keyboard)
        return
    await state.clear()
    await message.answer("✅ Режим отменён.", reply_markup=keyboard)

@dp.message(StateFilter(None, UserStates.main))
async def echo_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    age = data.get("age", 0)
    keyboard = get_main_keyboard() if age >= 14 else get_limited_keyboard()
    await message.answer("🤔 Не понимаю. Используй кнопки меню или /start.", reply_markup=keyboard)

async def main():
    logger.info("Starting bot...")
    try:
        while True:
            try:
                await dp.start_polling(bot)
            except Exception as e:
                logger.error(f"Polling error: {e}. Restarting in 5 seconds...")
                await asyncio.sleep(5)
                continue
    finally:
        await bot.session.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
