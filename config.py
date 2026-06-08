import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Конфигурация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения! Проверьте файл .env")

# GigaChat API (получение токена через OAuth)
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID", "")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET", "")

# ЯндексGPT API
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

# Реферальная ссылка (обязательна)
REF_LINK = os.getenv("REF_LINK")

if not REF_LINK:
    raise ValueError("REF_LINK не найден в переменных окружения! Проверьте файл .env")
