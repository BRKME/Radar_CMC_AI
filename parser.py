"""
Парсер для CoinMarketCap AI - VERSION 2.0.0 (with Alpha Take)
✅ 24/7 публикации по умному расписанию
✅ Отслеживание истории публикаций
✅ Динамические слоты с fallback на самый старый вопрос
✅ Группировка вариаций вопросов (up/down market)
✅ Retry логика и обработка ошибок
✅ Полное логирование и обработка edge cases
✅ OpenAI Alpha Take генерация (NEW в v2.0.0)
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import time
import json
import traceback
from datetime import datetime, timezone
import requests
import os
import sys
import random
import logging
import tweepy
from io import BytesIO
import tempfile
import platform
import re

# Пытаемся импортировать fcntl (только Unix) - FIX BUG #15
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    # На Windows fcntl недоступен - используем альтернативный механизм

# Импорт модуля улучшенного форматирования
from formatting import send_improved, __version__ as formatting_version

# Импорт OpenAI интеграции (NEW в v2.0.0)
from openai_cmc_integration import (
    get_ai_alpha_take,
    enhance_caption_with_alpha_take,
    enhance_twitter_with_alpha_take
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Глобальные настройки
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '2'))

# Telegram настройки
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Twitter API настройки (только из Secrets)
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# Включить/выключить Twitter (для тестирования)
TWITTER_ENABLED = os.getenv('TWITTER_ENABLED', 'true').lower() == 'true'

# OpenAI Alpha Take настройки (NEW в v2.0.0)
ALPHA_TAKE_ENABLED = os.getenv('ALPHA_TAKE_ENABLED', 'true').lower() == 'true'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# GitHub настройки для картинок
GITHUB_IMAGES_URL = "https://raw.githubusercontent.com/BRKME/coinmarketcap-parser/main/Images1/"
IMAGE_FILES = [f"{i}.jpg" for i in range(10, 151)]

# Расписание публикаций (час UTC : тип вопроса)
SCHEDULE = {
    0: None,
    1: None,
    2: None,
    3: None,
    4: None,
    5: None,
    6: "sentiment",      # 06:30 (запуск в 06:05, но логически 06:30)
    7: None,
    8: "market_direction",  # 08:00
    9: "DYNAMIC",        # 09:30
    10: None,
    11: None,
    12: None,
    13: "kols",          # 13:00
    14: "market_direction",  # 14:30
    15: None,
    16: "narratives",    # 16:00
    17: None,
    18: "sentiment",     # 18:00
    19: "events",        # 19:30
    20: None,
    21: "DYNAMIC",       # 21:00
    22: "market_direction",  # 22:30
    23: "narratives"     # 23:30
}

# Группы вопросов (для обработки вариаций)
QUESTION_GROUPS = {
    "market_direction": [
        "Why is the market up today?",
        "Why is the market down today?"
    ],
    "kols": ["What are KOLs discussing?"],
    "sentiment": ["What is the market sentiment?"],
    "events": ["What upcoming events may impact crypto?"],
    "bullish": ["What cryptos are showing bullish momentum?"],
    "narratives": ["What are the trending narratives?"],
    "altcoins": ["Are altcoins outperforming Bitcoin?"]
}

# Маппинг вопросов на заголовки и хэштеги для Telegram
QUESTION_DISPLAY_CONFIG = {
    "What are KOLs discussing?": {
        "title": "Crypto Insights",
        "hashtags": "#CryptoTwitter #KOLs #Alpha"
    },
    "What is the market sentiment?": {
        "title": "Daily Market Sentiment",
        "hashtags": "#FearAndGreed #CryptoSentiment #Bitcoin"
    },
    "What upcoming events may impact crypto?": {
        "title": "Upcoming Crypto Events",
        "hashtags": "#CryptoEvents #CryptoCalendar"
    },
    "What cryptos are showing bullish momentum?": {
        "title": "Bullish Crypto Watchlist",
        "hashtags": "#Altseason #Bullish #CryptoGems"
    },
    "What are the trending narratives?": {
        "title": "Trending Crypto Narratives",
        "hashtags": "#CryptoNarratives #RWA #AIcrypto"
    },
    "Why is the market up today?": {
        "title": "Market Analysis",
        "hashtags": "#Bitcoin #CryptoMarket #BullRun"
    },
    "Why is the market down today?": {
        "title": "Market Analysis",
        "hashtags": "#Bitcoin #CryptoMarket #Correction"
    },
    "Are altcoins outperforming Bitcoin?": {
        "title": "Altcoin Performance",
        "hashtags": "#Altcoins #Bitcoin #AltcoinSeason"
    }
}

def get_question_group(question_text):
    """Определяет к какой группе относится вопрос"""
    if not question_text:
        return "dynamic"
    
    question_lower = question_text.lower()
    
    # Проверяем market direction (up/down)
    if "why is the market" in question_lower and ("up" in question_lower or "down" in question_lower):
        return "market_direction"
    
    # Проверяем остальные группы
    if "kol" in question_lower:
        return "kols"
    if "sentiment" in question_lower:
        return "sentiment"
    if "upcoming events" in question_lower or "events" in question_lower and "impact" in question_lower:
        return "events"
    if "bullish" in question_lower and "momentum" in question_lower:
        return "bullish"
    if "trending narratives" in question_lower or "narratives" in question_lower:
        return "narratives"
    if "altcoins" in question_lower and "bitcoin" in question_lower:
        return "altcoins"
    
    return "dynamic"

def get_lock_file_path():
    """Возвращает путь к lock-файлу (кросс-платформенный) - FIX BUG #16"""
    if platform.system() == 'Windows':
        return os.path.join(tempfile.gettempdir(), 'cmc_parser.lock')
    else:
        return '/tmp/cmc_parser.lock'

def is_process_running(pid):
    """Проверяет что процесс с PID запущен - FIX BUG #18"""
    try:
        os.kill(pid, 0)  # Signal 0 = проверка существования
        return True
    except (OSError, ProcessLookupError):
        return False

def acquire_lock():
    """
    Создает lock-файл для предотвращения параллельного запуска
    FIX BUG #12, #15, #16, #18
    Возвращает (file_handle, path) или (None, None) если уже запущен
    """
    lock_path = get_lock_file_path()
    
    # Проверяем существующий lock (FIX BUG #18 - stale lock)
    if os.path.exists(lock_path):
        try:
            with open(lock_path, 'r') as f:
                content = f.read().strip()
                if content:
                    lines = content.split('\n')
                    try:
                        old_pid = int(lines[0])
                        
                        # Проверяем что процесс жив
                        if is_process_running(old_pid):
                            logger.error(f"✗ Парсер уже запущен (PID: {old_pid})")
                            return None, None
                        else:
                            logger.warning(f"⚠️ Найден stale lock от процесса {old_pid}, удаляю")
                            os.remove(lock_path)
                    except (ValueError, IndexError):
                        logger.warning(f"⚠️ Поврежденный lock-файл, удаляю")
                        os.remove(lock_path)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка чтения lock-файла: {e}, удаляю")
            try:
                os.remove(lock_path)
            except:
                pass
    
    # Создаем новый lock
    try:
        lock_file = open(lock_path, 'w')
        
        # Используем fcntl только если доступен (Unix)
        if HAS_FCNTL:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                lock_file.close()
                return None, None
        
        lock_file.write(f"{os.getpid()}\n{datetime.now(timezone.utc).isoformat()}")
        lock_file.flush()
        
        logger.info(f"✓ Lock-файл создан: {lock_path}")
        return lock_file, lock_path
        
    except Exception as e:
        logger.error(f"✗ Ошибка создания lock-файла: {e}")
        return None, None

def release_lock(lock_file, lock_path):
    """Освобождает lock-файл - FIX BUG #17"""
    try:
        if lock_file:
            if HAS_FCNTL:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
                except:
                    pass
            lock_file.close()
        
        if lock_path and os.path.exists(lock_path):
            os.remove(lock_path)
            logger.info(f"✓ Lock-файл удален: {lock_path}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить lock-файл: {e}")

def get_twitter_length(text):
    """
    Вычисляет длину текста как Twitter (emoji = 2 символа) - FIX BUG #23
    """
    if not text:
        return 0
    
    # Паттерн для emoji
    emoji_pattern = re.compile("["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+", flags=re.UNICODE)
    
    emoji_count = len(emoji_pattern.findall(text))
    return len(text) + emoji_count  # Каждый emoji добавляет +1

def validate_telegram_credentials():
    """Проверяет что Telegram токены валидные - FIX BUG #20"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram credentials не установлены")
        return False
    
    try:
        # Тестовый запрос getMe
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            logger.error(f"✗ Telegram токен невалидный: {response.status_code}")
            return False
        
        bot_info = response.json()
        if not bot_info.get('ok'):
            logger.error("✗ Telegram токен невалидный")
            return False
        
        bot_username = bot_info.get('result', {}).get('username', 'unknown')
        logger.info(f"✓ Telegram бот: @{bot_username}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Ошибка проверки Telegram credentials: {e}")
        return False

def validate_image_availability(sample_size=3):
    """Проверяет что картинки доступны (выборочно) - FIX BUG #21, #25"""
    if not IMAGE_FILES:
        logger.warning("⚠️ Список картинок пуст")
        logger.warning("   Публикация будет без картинок (только текст)")
        return True  # Не критично, можно продолжать без картинок
    
    logger.info(f"🔍 Проверка доступности картинок ({sample_size} из {len(IMAGE_FILES)})...")
    
    # Проверяем случайные картинки
    sample = random.sample(IMAGE_FILES, min(sample_size, len(IMAGE_FILES)))
    
    if not sample:
        logger.warning("⚠️ Нечего проверять")
        return True
    
    failed = 0
    for img in sample:
        url = GITHUB_IMAGES_URL + img
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                logger.info(f"  ✓ {img}")
            else:
                logger.warning(f"  ⚠️ {img} - статус {response.status_code}")
                failed += 1
        except Exception as e:
            logger.warning(f"  ✗ {img} - ошибка: {e}")
            failed += 1
    
    if failed == len(sample):
        logger.error("✗ Все проверенные картинки недоступны!")
        logger.error(f"   Проверьте URL: {GITHUB_IMAGES_URL}")
        logger.warning("   Продолжаем без картинок (только текст)")
        return True  # Не блокируем выполнение
    elif failed > 0:
        logger.warning(f"⚠️ {failed}/{len(sample)} картинок недоступны (продолжаем)")
        return True
    else:
        logger.info(f"✓ Картинки доступны")
        return True

def validate_display_config():
    """
    Валидирует конфигурацию отображения (FIX BUG #7, #9, #10)
    Проверяет что заголовки и хэштеги не слишком длинные
    """
    logger.info("🔍 Валидация конфигурации отображения...")
    
    warnings_count = 0
    errors_count = 0
    
    for question, config in QUESTION_DISPLAY_CONFIG.items():
        title = config.get("title", "")
        hashtags = config.get("hashtags", "")
        
        # Проверка длины заголовка
        if len(title) > 50:
            logger.error(f"✗ Слишком длинный заголовок для '{question[:30]}...': {len(title)} символов (максимум 50)")
            errors_count += 1
        elif len(title) > 40:
            logger.warning(f"⚠️ Длинный заголовок для '{question[:30]}...': {len(title)} символов (рекомендуется < 40)")
            warnings_count += 1
        
        # Проверка длины хэштегов (FIX BUG #10)
        if len(hashtags) > 120:
            logger.error(f"✗ Критически длинные хэштеги для '{question[:30]}...': {len(hashtags)} символов (максимум 120)")
            errors_count += 1
        elif len(hashtags) > 80:
            logger.warning(f"⚠️ Длинные хэштеги для '{question[:30]}...': {len(hashtags)} символов (рекомендуется < 80)")
            warnings_count += 1
        
        # Проверка места для текста (минимум 100 символов!)
        min_text_space = 270 - len(title) - len(hashtags) - 6
        if min_text_space < 100:
            logger.error(f"✗ Недостаточно места для текста в '{question[:30]}...': {min_text_space} символов (минимум 100)")
            logger.error(f"   Заголовок: {len(title)} + Хэштеги: {len(hashtags)} = слишком много!")
            errors_count += 1
    
    if errors_count > 0:
        logger.error(f"✗ Найдено {errors_count} критических ошибок в конфигурации")
        logger.error(f"   Исправьте QUESTION_DISPLAY_CONFIG перед запуском!")
    elif warnings_count > 0:
        logger.warning(f"⚠️ Конфигурация валидна с {warnings_count} предупреждениями")
    else:
        logger.info("✓ Конфигурация полностью валидна")
    
    return errors_count == 0

def load_publication_history():
    """Загружает историю публикаций из JSON файла"""
    try:
        if os.path.exists('publication_history.json'):
            with open('publication_history.json', 'r', encoding='utf-8') as f:
                history = json.load(f)
                logger.info(f"✓ История публикаций загружена: {len(history.get('last_published', {}))} групп")
                return history
    except Exception as e:
        logger.warning(f"⚠️ Ошибка загрузки истории: {e}")
    
    logger.info("📝 Создание новой истории публикаций")
    return {
        "last_published": {},
        "last_dynamic_question": "",
        "dynamic_published_at": ""
    }

def save_publication_history(history):
    """Сохраняет историю публикаций в JSON файл"""
    try:
        with open('publication_history.json', 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.info("✓ История публикаций обновлена")
        return True
    except Exception as e:
        logger.error(f"✗ Ошибка сохранения истории: {e}")
        return False

def get_oldest_question_group(history):
    """Находит группу вопроса которая публиковалась дольше всего назад"""
    last_published = history.get("last_published", {})
    
    all_groups = ["kols", "sentiment", "market_direction", "events", "bullish", "narratives", "altcoins"]
    
    if not last_published:
        logger.info("📊 История пуста, возвращаю 'kols'")
        return "kols"
    
    oldest_group = None
    oldest_time = None
    
    for group in all_groups:
        timestamp_str = last_published.get(group)
        
        if not timestamp_str:
            logger.info(f"📊 Группа '{group}' никогда не публиковалась")
            return group
            
        try:
            pub_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if oldest_time is None or pub_time < oldest_time:
                oldest_time = pub_time
                oldest_group = group
        except Exception as e:
            logger.warning(f"⚠️ Ошибка парсинга даты для {group}: {e}")
            return group
    
    logger.info(f"📊 Самая старая группа: {oldest_group} (опубликована {oldest_time})")
    return oldest_group if oldest_group else "kols"

def find_question_by_group(questions_list, group_name):
    """Находит вопрос из списка по группе"""
    if not questions_list:
        logger.warning("⚠️ Пустой список вопросов")
        return None
    
    for q in questions_list:
        if get_question_group(q) == group_name:
            logger.info(f"✓ Найден вопрос для группы '{group_name}': {q}")
            return q
    
    logger.warning(f"⚠️ Не найден вопрос для группы '{group_name}'")
    return None

def send_telegram_message(message, parse_mode='HTML'):
    """Отправляет сообщение в Telegram с разбивкой на части при необходимости"""
    try:
        # Проверка на пустые значения
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN.strip() == "" or TELEGRAM_CHAT_ID.strip() == "":
            logger.error("✗ Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
            return False
        
        max_length = 4000
        
        if len(message) <= max_length:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': parse_mode
            }
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code == 200:
                logger.info("✓ Сообщение отправлено в Telegram")
                return True
            else:
                logger.error(f"✗ Ошибка отправки в Telegram: {response.status_code} - {response.text}")
                return False
        else:
            logger.info(f"📨 Сообщение длинное ({len(message)} chars), разбиваю на части...")
            parts = []
            current_part = ""
            
            for line in message.split('\n'):
                if len(current_part) + len(line) + 1 > max_length:
                    if current_part:
                        parts.append(current_part)
                        current_part = line
                    else:
                        for i in range(0, len(line), max_length - 100):
                            parts.append(line[i:i + max_length - 100])
                else:
                    current_part = current_part + "\n" + line if current_part else line
            
            if current_part:
                parts.append(current_part)
            
            for i, part in enumerate(parts, 1):
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': part,
                    'parse_mode': parse_mode
                }
                response = requests.post(url, data=payload, timeout=10)
                logger.info(f"  ✓ Часть {i}/{len(parts)} отправлена")
                time.sleep(0.5)
            
            return True
            
    except Exception as e:
        logger.error(f"✗ Ошибка при отправке в Telegram: {e}")
        traceback.print_exc()
        return False

def send_telegram_photo_with_caption(photo_url, caption, parse_mode='HTML'):
    """Отправляет фото с подписью в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        
        logger.info(f"🔍 Попытка отправить фото: {photo_url}")
        logger.info(f"📏 Длина caption: {len(caption)} символов")
        
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'photo': photo_url
        }
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info("✓ Фото отправлено в Telegram")
            time.sleep(1)
            send_telegram_message(caption, parse_mode)
            return True
        else:
            logger.warning(f"⚠️ Ошибка отправки фото: {response.status_code} - {response.text}")
            logger.info("⚠️ Отправляю только текст без фото")
            send_telegram_message(caption, parse_mode)
            return False
                
    except Exception as e:
        logger.error(f"✗ Ошибка при отправке фото в Telegram: {e}")
        traceback.print_exc()
        logger.info("⚠️ Отправляю только текст без фото")
        send_telegram_message(caption, parse_mode)
        return False

def get_random_image_url():
    """Возвращает случайный URL картинки из GitHub"""
    random_image = random.choice(IMAGE_FILES)
    url = GITHUB_IMAGES_URL + random_image
    logger.info(f"🎨 Выбрана картинка: {random_image}")
    return url

def extract_tldr_from_answer(answer):
    """Извлекает только TLDR часть из ответа"""
    try:
        if not answer:
            return ""
        
        # Убираем строку "Researched for Xs"
        answer = '\n'.join([line for line in answer.split('\n') if not line.strip().startswith('Researched for')])
        
        # Ищем TLDR секцию
        if 'TLDR' in answer:
            tldr_start = answer.find('TLDR')
            deep_dive_start = answer.find('Deep Dive')
            
            if deep_dive_start != -1:
                tldr_section = answer[tldr_start:deep_dive_start].strip()
            else:
                tldr_section = answer[tldr_start:].strip()
            
            tldr_section = tldr_section.replace('TLDR', '', 1).strip()
            return tldr_section
        else:
            logger.warning("⚠️ TLDR не найден, возвращаю первые 500 символов")
            return answer[:500] + ("..." if len(answer) > 500 else "")
            
    except Exception as e:
        logger.error(f"⚠️ Ошибка извлечения TLDR: {e}")
        return answer[:500] + ("..." if len(answer) > 500 else "")

def clean_question_specific_text(question, text):
    """Убирает специфичные для вопросов ненужные строки"""
    try:
        if not text:
            return text
        
        cleaners = [
            ("What upcoming events may impact crypto?", 
             "These are the upcoming crypto events that may impact crypto the most:"),
            ("What cryptos are showing bullish momentum?", 
             "Here are the trending cryptos based on CoinMarketCap's evolving momentum algorithm (news, social, price momentum)"),
            ("What are the trending narratives?", 
             "Here are the trending narratives based on CoinMarketCap's evolving narrative algorithm (price, news, social momentum):")
        ]
        
        for question_pattern, text_to_remove in cleaners:
            if question_pattern in question:
                text = text.replace(text_to_remove, "").strip()
        
        return text
    except Exception as e:
        logger.error(f"⚠️ Ошибка очистки текста: {e}")
        return text

def smart_shorten_for_twitter(text, title, hashtags, max_total=270):
    """
    Умное сокращение текста для Twitter (макс 280 символов)
    Сохраняет полные предложения и не обрезает слова
    FIX BUG #23 - учитывает emoji как 2 символа
    """
    import re
    
    # Резервируем место под заголовок, хэштеги и форматирование
    # Формат: "Title\n\n[text]\n\n#hashtags"
    # Используем get_twitter_length для правильного подсчета с emoji
    reserved = get_twitter_length(title) + get_twitter_length(hashtags) + 6
    available_for_text = max_total - reserved
    
    # Защита от слишком длинных заголовков/хэштегов (FIX BUG #8)
    # Минимум 100 символов для контента (было 50 - слишком мало!)
    if available_for_text < 100:
        logger.error(f"✗ Недостаточно места для текста: {available_for_text} символов")
        logger.error(f"   Заголовок: {get_twitter_length(title)} символов (Twitter length)")
        logger.error(f"   Хэштеги: {get_twitter_length(hashtags)} символов (Twitter length)")
        
        # Экстренная мера: агрессивно сокращаем хэштеги
        if get_twitter_length(hashtags) > 80:
            logger.warning("   Сокращаю хэштеги до первых 3-х для освобождения места")
            hashtags_list = hashtags.split()[:3]
            hashtags = " ".join(hashtags_list)
            logger.warning(f"   Хэштеги сокращены до: {hashtags}")
            
            reserved = get_twitter_length(title) + get_twitter_length(hashtags) + 6
            available_for_text = max_total - reserved
            logger.info(f"   Теперь доступно: {available_for_text} символов")
        elif get_twitter_length(hashtags) > 50:
            hashtags_list = hashtags.split()[:5]
            hashtags = " ".join(hashtags_list)
            reserved = get_twitter_length(title) + get_twitter_length(hashtags) + 6
            available_for_text = max_total - reserved
    
    # Убираем избыточные пробелы, но сохраняем структуру (FIX BUG #5)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    text = text.strip()
    
    # Если текст влезает полностью
    if get_twitter_length(text) <= available_for_text:
        return text
    
    # Разбиваем на предложения
    sentences = re.split(r'([.!?]+\s*)', text)
    sentences = ["".join(sentences[i:i+2]).strip() 
                 for i in range(0, len(sentences)-1, 2) if sentences[i].strip()]
    
    # Собираем предложения пока влезают
    result = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        sent_length = get_twitter_length(sentence)
        
        if current_length + sent_length + 1 <= available_for_text:
            result.append(sentence)
            current_length += sent_length + 1
        else:
            if not result:
                # Обрезаем по последнему слову
                words = sentence.split()
                shortened = []
                for word in words:
                    test_text = " ".join(shortened + [word])
                    if get_twitter_length(test_text) + 3 <= available_for_text:
                        shortened.append(word)
                    else:
                        break
                if shortened:
                    return " ".join(shortened) + "..."
                else:
                    return sentence[:available_for_text-3] + "..."
            break
    
    return " ".join(result)

def init_twitter_client():
    """Инициализирует Twitter API клиент"""
    try:
        # Проверяем обязательные ключи (Bearer Token опциональный!)
        if not all([TWITTER_API_KEY, TWITTER_API_SECRET, 
                    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
            logger.warning("⚠️ Twitter API ключи не установлены (нужны: API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)")
            return None
        
        # Bearer Token опциональный - нужен только для read операций
        if not TWITTER_BEARER_TOKEN:
            logger.info("ℹ️  Bearer Token не установлен (опционально для постинга)")
        
        # Tweepy v2 Client для API v2
        client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,  # Может быть None - это ОК для постинга
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )
        
        # API v1.1 для загрузки медиа (картинок)
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY,
            TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_TOKEN_SECRET
        )
        api = tweepy.API(auth)
        
        logger.info("✓ Twitter API клиент инициализирован")
        return {"client": client, "api": api}
        
    except Exception as e:
        logger.error(f"✗ Ошибка инициализации Twitter API: {e}")
        return None

def send_twitter_thread(twitter_content, image_url):
    """
    Отправляет Twitter контент (тред или одиночный твит)
    
    Args:
        twitter_content: dict с ключами:
            - mode: "thread" или "single"
            - tweets: list (для thread)
            - tweet: str (для single)
        image_url: URL картинки
    
    Returns:
        bool: True если успешно
    """
    try:
        if not TWITTER_ENABLED:
            logger.info("ℹ️  Twitter отключен")
            return False
        
        twitter = init_twitter_client()
        if not twitter:
            logger.error("✗ Не удалось инициализировать Twitter клиент")
            return False
        
        client = twitter["client"]
        api = twitter["api"]
        
        # Загружаем картинку
        media_id = None
        if image_url:
            try:
                logger.info(f"🖼️  Загрузка картинки...")
                response = requests.get(image_url, timeout=30)
                if response.status_code == 200:
                    media = api.media_upload(filename="image.jpg", file=BytesIO(response.content))
                    media_id = media.media_id
                    logger.info(f"✓ Картинка загружена")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки картинки: {e}")
        
        mode = twitter_content.get("mode", "single")
        
        # РЕЖИМ: ТРЕД
        if mode == "thread" and "tweets" in twitter_content:
            tweets = twitter_content["tweets"]
            
            if not tweets or len(tweets) < 2:
                logger.warning("⚠️ Тред слишком короткий, переключаюсь на single")
                mode = "single"
            else:
                logger.info(f"🧵 Публикация треда из {len(tweets)} твитов...")
                
                previous_tweet_id = None
                published_count = 0
                
                for i, tweet_text in enumerate(tweets, 1):
                    try:
                        logger.info(f"  📤 Твит {i}/{len(tweets)}: {len(tweet_text)} символов")
                        
                        if i == 1 and media_id:
                            response = client.create_tweet(text=tweet_text, media_ids=[media_id])
                        elif previous_tweet_id:
                            response = client.create_tweet(text=tweet_text, in_reply_to_tweet_id=previous_tweet_id)
                        else:
                            response = client.create_tweet(text=tweet_text)
                        
                        if response and hasattr(response, 'data'):
                            try:
                                if hasattr(response.data, 'get'):
                                    tweet_id = response.data.get('id')
                                elif hasattr(response.data, 'id'):
                                    tweet_id = response.data.id
                                else:
                                    tweet_id = response.data['id']
                                
                                if tweet_id:
                                    previous_tweet_id = tweet_id
                                    published_count += 1
                                    logger.info(f"    ✓ Твит {i} опубликован")
                                    
                                    if i < len(tweets):
                                        time.sleep(2)
                                else:
                                    logger.error(f"    ✗ Нет ID для твита {i}")
                                    break
                            except Exception as e:
                                logger.error(f"    ✗ Ошибка получения ID твита {i}: {e}")
                                break
                        else:
                            logger.error(f"    ✗ Пустой ответ для твита {i}")
                            break
                    
                    except tweepy.TweepyException as e:
                        error_str = str(e)
                        
                        if "rate limit" in error_str.lower() or "429" in error_str:
                            logger.warning(f"⚠️ Rate limit на твите {i}")
                            return published_count >= 1
                        
                        if "duplicate" in error_str.lower() or "187" in error_str:
                            logger.warning(f"⚠️ Твит {i} дубликат, пропускаем")
                            continue
                        
                        logger.error(f"✗ Ошибка публикации твита {i}: {e}")
                        return published_count >= 1
                
                if published_count >= 2:
                    logger.info(f"✓ Тред опубликован ({published_count} твитов)")
                    return True
                elif published_count == 1:
                    logger.warning("⚠️ Опубликован только 1 твит (не тред)")
                    return True
                else:
                    logger.error("✗ Не удалось опубликовать тред")
                    return False
        
        # РЕЖИМ: ОДИНОЧНЫЙ ТВИТ
        if mode == "single":
            tweet_text = twitter_content.get("tweet")
            
            if not tweet_text:
                logger.error("✗ Нет текста твита")
                return False
            
            logger.info(f"📏 Одиночный твит: {len(tweet_text)} символов")
            
            try:
                if media_id:
                    response = client.create_tweet(text=tweet_text, media_ids=[media_id])
                else:
                    response = client.create_tweet(text=tweet_text)
                
                if not response or not hasattr(response, 'data'):
                    logger.error("✗ Пустой ответ от Twitter API")
                    return False
                
                tweet_id = None
                try:
                    if hasattr(response.data, 'get'):
                        tweet_id = response.data.get('id')
                    elif hasattr(response.data, 'id'):
                        tweet_id = response.data.id
                    else:
                        tweet_id = response.data['id']
                except Exception as e:
                    logger.error(f"✗ Ошибка получения ID: {e}")
                    return False
                
                if tweet_id:
                    logger.info(f"✓ Твит опубликован (ID: {tweet_id})")
                    return True
                else:
                    logger.error("✗ Нет ID твита")
                    return False
                
            except tweepy.TweepyException as e:
                error_str = str(e)
                
                if "rate limit" in error_str.lower() or "429" in error_str:
                    logger.warning("⚠️ Rate limit")
                    return True
                
                if "duplicate" in error_str.lower() or "187" in error_str:
                    logger.warning("⚠️ Дубликат твита")
                    return True
                
                logger.error(f"✗ Ошибка: {e}")
                
                if media_id:
                    logger.info("🔄 Попытка без картинки...")
                    try:
                        response = client.create_tweet(text=tweet_text)
                        if response and hasattr(response, 'data'):
                            logger.info("✓ Опубликовано без картинки")
                            return True
                    except:
                        pass
                
                return False
    
    except Exception as e:
        logger.error(f"✗ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_question_answer_to_telegram(question, answer):
    """
    Отправляет вопрос и TLDR в Telegram с картинкой и Alpha Take (V2).
    Возвращает True если успешно.
    
    NEW в V2.0:
    - Генерация Alpha Take через OpenAI
    - Enhanced caption с Alpha Take + Context Tag
    - Улучшенное форматирование для Twitter
    """
    try:
        logger.info(f"\n📤 ОТПРАВКА (форматирование v{formatting_version})")
        
        # ==========================================
        # 1. ИЗВЛЕЧЕНИЕ И ОЧИСТКА КОНТЕНТА
        # ==========================================
        
        # Извлекаем TLDR
        tldr_text = extract_tldr_from_answer(answer)
        if not tldr_text:
            logger.error("✗ Пустой TLDR")
            return False
        
        # Очищаем текст
        tldr_text = clean_question_specific_text(question, tldr_text)
        if not tldr_text:
            logger.error("✗ Пустой текст после очистки")
            return False
        
        logger.info(f"  ✓ TLDR извлечен: {len(tldr_text)} символов")
        
        # ==========================================
        # 2. ПОЛУЧЕНИЕ КОНФИГУРАЦИИ
        # ==========================================
        
        config = QUESTION_DISPLAY_CONFIG.get(question, {
            "title": "Crypto Update",
            "hashtags": "#Crypto #Bitcoin"
        })
        
        title = config.get("title", "Crypto Update")
        hashtags = config.get("hashtags", "#Crypto")
        
        logger.info(f"  ✓ Заголовок: {title}")
        logger.info(f"  ✓ Хештеги: {hashtags}")
        
        # ==========================================
        # 3. ГЕНЕРАЦИЯ ALPHA TAKE (NEW В V2)
        # ==========================================
        
        ai_result = None
        
        if ALPHA_TAKE_ENABLED and OPENAI_API_KEY:
            logger.info("\n🤖 ГЕНЕРАЦИЯ ALPHA TAKE")
            logger.info(f"   Используем OpenAI для анализа...")
            
            try:
                ai_result = get_ai_alpha_take(
                    news_text=tldr_text,
                    question_context=question
                )
                
                if ai_result:
                    logger.info("✓ Alpha Take успешно сгенерирован:")
                    logger.info(f"   • Alpha Take: {ai_result.get('alpha_take', '')[:80]}...")
                    logger.info(f"   • Context Tag: {ai_result.get('context_tag', 'N/A')}")
                    logger.info(f"   • Hashtags: {ai_result.get('hashtags', 'N/A')}")
                else:
                    logger.warning("⚠️ Alpha Take не получен")
                    logger.warning("   Используем обычный формат публикации")
                    
            except Exception as e:
                logger.error(f"✗ Ошибка генерации Alpha Take: {e}")
                logger.warning("   Fallback на обычный формат")
                ai_result = None
        else:
            if not ALPHA_TAKE_ENABLED:
                logger.info("ℹ️  Alpha Take отключен (ALPHA_TAKE_ENABLED=false)")
            else:
                logger.warning("⚠️ OpenAI API ключ не установлен")
            logger.info("   Используем обычный формат публикации")
        
        # ==========================================
        # 4. ФОРМАТИРОВАНИЕ TELEGRAM CAPTION
        # ==========================================
        
        logger.info("\n📝 ФОРМАТИРОВАНИЕ КОНТЕНТА")
        
        if ai_result:
            # С Alpha Take - enhanced формат
            logger.info("   Режим: Enhanced (с Alpha Take)")
            telegram_caption = enhance_caption_with_alpha_take(
                title=title,
                text=tldr_text,
                hashtags_fallback=hashtags,
                ai_result=ai_result
            )
        else:
            # Без Alpha Take - старый формат
            logger.info("   Режим: Standard (без Alpha Take)")
            telegram_caption = f"<b>{title}</b>\n\n{tldr_text}\n\n{hashtags}"
        
        logger.info(f"  ✓ Telegram caption: {len(telegram_caption)} символов")
        
        # ==========================================
        # 5. ПОЛУЧЕНИЕ КАРТИНКИ
        # ==========================================
        
        image_url = get_random_image_url()
        logger.info(f"  ✓ Картинка выбрана: {image_url.split('/')[-1]}")
        
        # ==========================================
        # 6. ОТПРАВКА В TELEGRAM
        # ==========================================
        
        logger.info("\n📤 ОТПРАВКА В TELEGRAM")
        
        telegram_success = False
        try:
            telegram_success = send_telegram_photo_with_caption(
                photo_url=image_url,
                caption=telegram_caption,
                parse_mode='HTML'
            )
            
            if telegram_success:
                logger.info("✓ Telegram: Успешно отправлено")
            else:
                logger.error("✗ Telegram: Ошибка отправки")
                return False
                
        except Exception as e:
            logger.error(f"✗ Telegram ошибка: {e}")
            return False
        
        # Пауза между платформами
        time.sleep(2)
        
        # ==========================================
        # 7. ОТПРАВКА В TWITTER (ОПЦИОНАЛЬНО)
        # ==========================================
        
        if TWITTER_ENABLED and all([TWITTER_API_KEY, TWITTER_API_SECRET,
                                    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
            
            logger.info("\n🐦 ПОДГОТОВКА TWITTER КОНТЕНТА")
            
            try:
                # Если есть Alpha Take - используем его для Twitter
                if ai_result:
                    logger.info("   Используем Alpha Take для Twitter")
                    
                    twitter_text = enhance_twitter_with_alpha_take(
                        title=title,
                        alpha_take=ai_result.get('alpha_take', tldr_text),
                        context_tag=ai_result.get('context_tag'),
                        hashtags=ai_result.get('hashtags', hashtags)
                    )
                else:
                    logger.info("   Используем стандартное сокращение")
                    
                    # Без Alpha Take - обычное сокращение
                    twitter_text = smart_shorten_for_twitter(
                        text=tldr_text,
                        title=title,
                        hashtags=hashtags,
                        max_total=270
                    )
                    twitter_text = f"{title}\n\n{twitter_text}\n\n{hashtags}"
                
                # Формируем контент для Twitter
                twitter_content = {
                    "mode": "single",
                    "tweet": twitter_text
                }
                
                tweet_length = get_twitter_length(twitter_text)
                logger.info(f"  ✓ Tweet подготовлен: {tweet_length} символов")
                
                if tweet_length > 280:
                    logger.warning(f"  ⚠️ Tweet слишком длинный, дополнительное сокращение...")
                    twitter_text = twitter_text[:277] + "..."
                    twitter_content["tweet"] = twitter_text
                
                # Отправляем
                logger.info("\n📤 ОТПРАВКА В TWITTER")
                tw_success = send_twitter_thread(twitter_content, image_url)
                
                if tw_success:
                    logger.info("✓ Twitter: Успешно отправлено")
                else:
                    logger.warning("⚠️ Twitter: Ошибка отправки (не критично)")
                
            except Exception as e:
                logger.error(f"✗ Twitter ошибка: {e}")
                logger.warning("   Twitter публикация пропущена (не критично)")
        else:
            logger.info("\nℹ️  Twitter отключен или не настроен")
        
        # ==========================================
        # 8. ИТОГОВЫЙ ОТЧЕТ
        # ==========================================
        
        logger.info(f"\n{'='*50}")
        logger.info(f"📊 ИТОГОВЫЙ ОТЧЕТ:")
        logger.info(f"{'='*50}")
        logger.info(f"  Вопрос: {question[:50]}...")
        logger.info(f"  Заголовок: {title}")
        logger.info(f"  TLDR длина: {len(tldr_text)} символов")
        logger.info(f"  Telegram: ✓ Отправлено")
        logger.info(f"  Alpha Take: {'✓ Включен' if ai_result else '✗ Отключен'}")
        
        if ai_result:
            logger.info(f"  Context Tag: {ai_result.get('context_tag', 'N/A')}")
            logger.info(f"  AI Hashtags: {'✓ Да' if ai_result.get('hashtags') else '✗ Fallback'}")
        
        logger.info(f"{'='*50}\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА В ОТПРАВКЕ")
        logger.error(f"✗ Ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def accept_cookies(page):
    """Принимает cookies если баннер появился"""
    try:
        cookie_buttons = [
            'button:has-text("Accept Cookies and Continue")',
            'button:has-text("Accept All")',
            'button:has-text("Accept")',
            'text="Accept Cookies and Continue"'
        ]

        for selector in cookie_buttons:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    logger.info("✓ Cookie-баннер принят")
                    await asyncio.sleep(2)
                    return True
            except:
                continue

        return False
    except Exception as e:
        logger.warning(f"⚠️ Предупреждение при обработке cookies: {e}")
        return False

async def reset_to_question_list(page):
    """Возвращает страницу к состоянию со списком вопросов"""
    try:
        reset_selectors = [
            'button:has-text("New")',
            'button:has-text("Reset")',
            'button:has-text("Clear")',
            'a:has-text("New")',
            '[aria-label*="new"]',
            '[aria-label*="reset"]',
            '[title*="New"]',
            '[title*="Reset"]'
        ]

        for selector in reset_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    await asyncio.sleep(2)
                    logger.info("  ✓ Сброс чата выполнен")
                    return True
            except:
                continue

        logger.info("  ℹ️  Переход на базовый URL...")
        await page.goto('https://coinmarketcap.com/cmc-ai/ask/', wait_until='domcontentloaded', timeout=15000)
        await accept_cookies(page)
        await asyncio.sleep(3)
        return True

    except Exception as e:
        logger.warning(f"  ⚠️ Ошибка сброса: {e}")
        try:
            await page.goto('https://coinmarketcap.com/cmc-ai/ask/', timeout=15000)
            await asyncio.sleep(2)
            return True
        except:
            return False

async def get_ai_response(page, question_text):
    """Получает ответ AI используя точный селектор"""
    try:
        logger.info("  ⏳ Ожидание генерации ответа AI...")
        await asyncio.sleep(5)

        max_attempts = 25

        for attempt in range(max_attempts):
            try:
                assistant_container = await page.query_selector('div.MemoizedChatMessage_message-assistant-wrapper__eAoOF')

                if assistant_container:
                    full_text = await assistant_container.inner_text()

                    if (full_text and len(full_text) > 200 and 'TLDR' in full_text):
                        if full_text.startswith('BTC$'):
                            parts = full_text.split(question_text)
                            if len(parts) > 1:
                                full_text = question_text + parts[1]

                        logger.info(f"  ✓ Ответ найден на попытке {attempt + 1}")
                        return full_text.strip()

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                assistant_div = soup.find('div', class_=lambda x: x and 'message-assistant' in str(x))

                if assistant_div:
                    paragraphs = assistant_div.find_all('p')
                    if len(paragraphs) > 2:
                        full_answer = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                        if len(full_answer) > 200 and 'TLDR' in full_answer:
                            logger.info(f"  ✓ Ответ найден на попытке {attempt + 1} (BeautifulSoup)")
                            return full_answer

            except Exception as e:
                pass

            if attempt < max_attempts - 1:
                await asyncio.sleep(1)

            if (attempt + 1) % 5 == 0:
                logger.info(f"  ⏳ Попытка {attempt + 1}/{max_attempts}...")

        logger.warning("  ⚠️ Ответ не найден после всех попыток")
        return None

    except Exception as e:
        logger.error(f"  ❌ Ошибка: {e}")
        return None

async def click_and_get_response(page, question_text, attempt_num=1):
    """Кликает по кнопке с вопросом и получает ответ AI"""
    try:
        logger.info(f"\n🔍 Поиск кнопки: '{question_text}' (попытка {attempt_num})")

        button = await page.query_selector(f'text="{question_text}"')

        if not button:
            logger.error(f"✗ Кнопка не найдена")
            return None

        logger.info(f"✓ Кнопка найдена, выполняю клик...")
        await button.click()

        response = await get_ai_response(page, question_text)

        if response:
            logger.info(f"✓ Обработка завершена (длина ответа: {len(response)} символов)")
            return {
                'question': question_text,
                'answer': response,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'attempt': attempt_num,
                'length': len(response)
            }
        else:
            logger.error(f"✗ Ответ не получен")
            return None

    except Exception as e:
        logger.error(f"✗ Ошибка при клике: {e}")
        return None

async def get_all_questions(page):
    """Получает список всех доступных вопросов"""
    try:
        elements = await page.query_selector_all('div.BaseChip_labelWrapper__pQXPT')
        
        questions_list = []
        seen = set()
        
        for elem in elements:
            text = await elem.inner_text()
            text = text.strip()
            if text and text not in seen:
                questions_list.append(text)
                seen.add(text)
        
        logger.info(f"✓ Найдено уникальных вопросов: {len(questions_list)}")
        return questions_list
    except Exception as e:
        logger.error(f"✗ Ошибка получения списка вопросов: {e}")
        return []

async def main_parser():
    """Главная функция парсера с умным расписанием"""
    browser = None
    try:
        logger.info("="*70)
        logger.info("🚀 ЗАПУСК ПАРСЕРА COINMARKETCAP AI v2.0.0")
        logger.info("="*70)
        
        async with async_playwright() as p:
            logger.info("🌐 Загрузка страницы...")

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--single-process'
                ]
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )

            page = await context.new_page()

            for attempt in range(3):
                try:
                    await page.goto('https://coinmarketcap.com/cmc-ai/ask/', wait_until='domcontentloaded', timeout=20000)
                    logger.info("✓ Страница загружена")
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"⚠️ Попытка {attempt + 1} не удалась, пробую еще раз...")
                        await asyncio.sleep(3)
                    else:
                        raise

            logger.info("🍪 Проверка cookie-баннера...")
            await accept_cookies(page)

            logger.info("⏳ Ожидание загрузки контента (5 секунд)...")
            await asyncio.sleep(5)

            # Получаем список всех вопросов
            logger.info("\n🔍 ПОЛУЧЕНИЕ СПИСКА ВОПРОСОВ")
            questions_list = await get_all_questions(page)
            
            if not questions_list:
                raise Exception("Не найдено ни одного вопроса на странице!")
            
            for i, q in enumerate(questions_list, 1):
                group = get_question_group(q)
                logger.info(f"  {i}. {q} [{group}]")

            # Загружаем историю публикаций
            history = load_publication_history()
            
            # Определяем текущий час UTC
            current_hour = datetime.now(timezone.utc).hour
            scheduled_group = SCHEDULE.get(current_hour)
            
            if not scheduled_group:
                raise Exception(f"Нет расписания для часа {current_hour}")
            
            logger.info(f"\n⏰ Текущий час UTC: {current_hour}")
            logger.info(f"📅 По расписанию должна быть группа: {scheduled_group}")
            
            # Определяем какой вопрос публиковать
            question_to_publish = None
            
            if scheduled_group == "DYNAMIC":
                logger.info("\n🎯 Динамический слот!")
                
                # Находим динамический вопрос
                dynamic_question = None
                for q in questions_list:
                    if get_question_group(q) == "dynamic":
                        dynamic_question = q
                        break
                
                if dynamic_question:
                    last_dynamic = history.get("last_dynamic_question", "")
                    
                    if dynamic_question != last_dynamic:
                        logger.info(f"✨ Динамический вопрос изменился!")
                        logger.info(f"   Старый: {last_dynamic}")
                        logger.info(f"   Новый: {dynamic_question}")
                        question_to_publish = dynamic_question
                        
                        # Обновляем историю динамического вопроса
                        history["last_dynamic_question"] = dynamic_question
                    else:
                        logger.info(f"⚠️ Динамический вопрос не изменился: {dynamic_question}")
                        logger.info(f"   Ищем самый старый вопрос...")
                        oldest_group = get_oldest_question_group(history)
                        question_to_publish = find_question_by_group(questions_list, oldest_group)
                        if question_to_publish:
                            scheduled_group = oldest_group
                        else:
                            logger.warning(f"⚠️ Не найден вопрос для группы {oldest_group}, публикуем динамический")
                            question_to_publish = dynamic_question
                            scheduled_group = "DYNAMIC"
                else:
                    logger.warning("⚠️ Динамический вопрос не найден на странице")
                    logger.info("   Публикуем самый старый вопрос...")
                    oldest_group = get_oldest_question_group(history)
                    question_to_publish = find_question_by_group(questions_list, oldest_group)
                    if question_to_publish:
                        scheduled_group = oldest_group
                    else:
                        raise Exception(f"Критическая ошибка: не найден вопрос для {oldest_group}")
            else:
                # Обычный слот по расписанию
                question_to_publish = find_question_by_group(questions_list, scheduled_group)
            
            # Fallback если вопрос для группы не найден (FIX BUG #14)
            if not question_to_publish:
                logger.warning(f"⚠️ Не найден вопрос для группы '{scheduled_group}'")
                logger.warning(f"   Пытаюсь найти любой доступный вопрос...")
                
                # Пробуем найти хоть что-то из стандартных групп
                for fallback_group in ["kols", "sentiment", "events", "bullish", "narratives", "altcoins"]:
                    question_to_publish = find_question_by_group(questions_list, fallback_group)
                    if question_to_publish:
                        logger.info(f"✓ Найден вопрос из группы '{fallback_group}': {question_to_publish}")
                        scheduled_group = fallback_group
                        break
                
                # Если совсем ничего - берем первый доступный
                if not question_to_publish and questions_list:
                    question_to_publish = questions_list[0]
                    scheduled_group = get_question_group(question_to_publish)
                    logger.info(f"✓ Выбран первый доступный вопрос: {question_to_publish}")
            
            if not question_to_publish:
                raise Exception("Критическая ошибка: на странице нет вопросов!")
            
            logger.info(f"\n✅ Выбран вопрос для публикации: {question_to_publish}")
            
            # Парсим ответ на выбранный вопрос с повторными попытками
            result = None
            for retry in range(MAX_RETRIES + 1):
                if retry > 0:
                    logger.info(f"\n🔄 Повторная попытка {retry}/{MAX_RETRIES}")
                    await reset_to_question_list(page)
                    await asyncio.sleep(3)
                
                result = await click_and_get_response(page, question_to_publish, attempt_num=retry + 1)
                
                if result:
                    break
            
            if not result:
                raise Exception(f"Не удалось получить ответ после {MAX_RETRIES + 1} попыток")
            
            # Отправляем в Telegram
            logger.info("\n📤 ОТПРАВКА В TELEGRAM")
            send_success = send_question_answer_to_telegram(result['question'], result['answer'])
            
            if not send_success:
                logger.warning("⚠️ Ошибка отправки в Telegram, но продолжаем")
            
            # Обновляем историю публикаций
            if scheduled_group == "DYNAMIC":
                history["dynamic_published_at"] = datetime.now(timezone.utc).isoformat()
                history["last_published"]["dynamic"] = datetime.now(timezone.utc).isoformat()
            else:
                history["last_published"][scheduled_group] = datetime.now(timezone.utc).isoformat()
            
            # Сохраняем дополнительную информацию для отладки
            history["last_publication"] = {
                "question": result['question'],
                "group": scheduled_group,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "hour_utc": current_hour,
                "answer_length": result['length']
            }
            
            save_publication_history(history)
            
            logger.info(f"\n🎯 ИТОГ")
            logger.info(f"  ✓ Вопрос: {result['question']}")
            logger.info(f"  ✓ Группа: {scheduled_group}")
            logger.info(f"  ✓ Длина ответа: {result['length']} символов")
            logger.info(f"  ✓ Опубликовано в Telegram: {send_success}")
            logger.info("="*70)

            await browser.close()
            logger.info("✓ Браузер закрыт\n")
            
            return True

    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(traceback.format_exc())
        
        # Пытаемся закрыть браузер при ошибке
        try:
            if browser:
                await browser.close()
        except:
            pass
        
        # Ошибки только в логах (НЕ спамим в Telegram)
        logger.error("=" * 70)
        logger.error("Ошибка залогирована в parser.log")
        logger.error("Telegram уведомление ОТКЛЮЧЕНО")
        logger.error("=" * 70)
        
        return False

def main():
    """Точка входа в программу"""
    lock_file = None
    lock_path = None
    
    try:
        # Проверка lock-файла (FIX BUG #12, #15, #16, #17, #18)
        lock_file, lock_path = acquire_lock()
        if not lock_file:
            logger.error("\n✗ Парсер уже запущен!")
            logger.error(f"   Дождитесь завершения предыдущего запуска или удалите {get_lock_file_path()}")
            sys.exit(2)  # Exit code 2 = already running
        
        logger.info("\n" + "="*70)
        logger.info("🤖 COINMARKETCAP AI PARSER v2.0.0 - WITH ALPHA TAKE")
        logger.info("="*70)
        logger.info(f"📅 Дата запуска: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logger.info(f"💻 Платформа: {platform.system()} {platform.release()}")
        logger.info(f"🔒 Lock файл: {lock_path}")
        logger.info(f"⚙️  Настройки:")
        logger.info(f"   • MAX_RETRIES: {MAX_RETRIES}")
        logger.info(f"   • Telegram Bot Token: {'✓ Установлен' if TELEGRAM_BOT_TOKEN else '✗ Не установлен'}")
        logger.info(f"   • Telegram Chat ID: {'✓ Установлен' if TELEGRAM_CHAT_ID else '✗ Не установлен'}")
        logger.info(f"   • Twitter API: {'✓ Установлен' if all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]) else '✗ Не установлен'}")
        logger.info(f"   • Twitter Enabled: {'✓ Да' if TWITTER_ENABLED else '✗ Нет'}")
        logger.info(f"   • Alpha Take Enabled: {'✓ Да' if ALPHA_TAKE_ENABLED else '✗ Нет'}")
        logger.info(f"   • OpenAI API Key: {'✓ Установлен' if OPENAI_API_KEY else '✗ Не установлен'}")
        logger.info(f"   • fcntl available: {'✓ Да' if HAS_FCNTL else '✗ Нет (Windows)'}")
        logger.info("="*70 + "\n")
        
        # Валидация Telegram credentials (FIX BUG #20)
        if not validate_telegram_credentials():
            logger.error("✗ КРИТИЧЕСКАЯ ОШИБКА: Невалидные Telegram credentials!")
            logger.error("   Проверьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")
            release_lock(lock_file, lock_path)
            sys.exit(1)
        
        # Валидация конфигурации перед запуском (FIX BUG #9)
        if not validate_display_config():
            logger.error("\n✗ КРИТИЧЕСКАЯ ОШИБКА: Конфигурация невалидна!")
            logger.error("   Исправьте ошибки в QUESTION_DISPLAY_CONFIG и перезапустите")
            release_lock(lock_file, lock_path)
            sys.exit(1)
        
        # Проверка доступности картинок (FIX BUG #21)
        validate_image_availability(sample_size=3)
        
        logger.info("")
        
        # Запускаем основной парсер
        success = asyncio.run(main_parser())
        
        # Освобождаем lock
        release_lock(lock_file, lock_path)
        
        if success:
            logger.info("\n✅ ПАРСИНГ ЗАВЕРШЕН УСПЕШНО!")
            sys.exit(0)
        else:
            logger.error("\n❌ ПАРСИНГ ЗАВЕРШЕН С ОШИБКОЙ!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Парсинг прерван пользователем (Ctrl+C)")
        release_lock(lock_file, lock_path)
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА В MAIN: {e}")
        logger.error(traceback.format_exc())
        release_lock(lock_file, lock_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
