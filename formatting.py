"""
formatting.py - Модуль улучшенного форматирования для Telegram и Twitter
Version: 3.1.2
Senior QA Approved - Production Ready

ОБНОВЛЕНО В v3.1.2:
- Twitter треды показывают 2-3 ключевых пункта (было: только 1)
- Умная разбивка контента на твиты
- Адаптивное сокращение если не влезает

ОБНОВЛЕНО В v3.1.1:
- Оптимизация для Twitter Free tier
- Мини-треды: максимум 3 твита
- Увеличена пауза между твитами: 15 секунд
- Адаптация под rate limits

ИСПРАВЛЕНО В v3.1.0:
- Исправлен конфликт параметров send_twitter_fn
- Оптимизированы импорты
- Добавлена защита от пустых тредов
- Улучшен fallback на одиночный твит

НОВОЕ В v3.0.0:
- 🧵 Поддержка Twitter тредов
- 📊 Умная разбивка по смысловым блокам
- 🎯 Автонумерация твитов
- ⚡ Fallback на одиночный твит
"""

import re
import time
import logging

logger = logging.getLogger(__name__)

# ========================================
# ВЕРСИЯ И НАСТРОЙКИ
# ========================================

__version__ = "3.1.2"

# НАСТРОЙКА РЕЖИМА TWITTER
TWITTER_MODE = "thread"  # "thread" или "single"

# ========================================
# КОНСТАНТЫ
# ========================================

MAX_TEXT_LENGTH = 5000
MAX_LINE_COUNT = 100
MAX_EMOJI_COUNT = 3
EMOJI_DETECTION_TEXT_LIMIT = 2000

MIN_TWITTER_SPACE = 50
MAX_TWITTER_LENGTH = 280
MAX_TELEGRAM_LENGTH = 4000
MAX_THREAD_TWEETS = 3  # Оптимизировано для Free tier (было 8)

# Пауза между твитами (увеличена для Free tier rate limits)
TWEET_DELAY = 15  # секунды (было 2)

# Эмодзи для заголовков
TITLE_EMOJI_MAP = {
    "Crypto Insights": "💡",
    "Market Analysis": "📊",
    "Daily Market Sentiment": "🎭",
    "Upcoming Crypto Events": "📅",
    "Bullish Crypto Watchlist": "🚀",
    "Trending Crypto Narratives": "🔥",
    "Altcoin Performance": "⚡"
}

# Контекстные паттерны
CONTEXT_PATTERNS = [
    ("bullish|rally|surge|pump|moon", "🚀", 1),
    ("bearish|dump|crash|decline|drop", "🐻", 1),
    ("liquidation|liquidated|rekt", "🔥", 2),
    ("bitcoin|btc", "₿", 3),
    ("ethereum|eth", "💎", 3),
    ("solana|sol", "🦎", 3),
    ("whale|whales", "🐋", 2),
    ("ai|artificial intelligence", "🤖", 2),
    ("defi|decentralized finance", "✨", 3),
]

# Compiled regex
CRYPTO_PRICE_PATTERN = re.compile(r'^[A-Z]{2,10}\s*\([+-]?\d')
LIST_ITEM_PATTERN = re.compile(r'^[\-•\*]\s+|^\d+\.\s+')

# ========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ========================================

def safe_str(value, default="", max_length=None):
    """Безопасное преобразование в строку"""
    if value is None:
        return default
    try:
        result = str(value).strip()
    except Exception:
        return default
    if max_length and len(result) > max_length:
        result = result[:max_length]
    return result


def get_twitter_length(text):
    """Вычисляет длину текста для Twitter (emoji = 2 символа)"""
    if not text:
        return 0
    emoji_pattern = re.compile("["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    emoji_count = len(emoji_pattern.findall(text))
    return len(text) + emoji_count


def get_context_emojis(text, max_count=MAX_EMOJI_COUNT):
    """Определяет контекстные эмодзи"""
    if not text:
        return []
    
    text_lower = text[:EMOJI_DETECTION_TEXT_LIMIT].lower()
    found = []
    
    for pattern, emoji, priority in sorted(CONTEXT_PATTERNS, key=lambda x: x[2]):
        if emoji in [e for e, p in found]:
            continue
        
        words = pattern.split("|")
        if any(word in text_lower for word in words):
            found.append((emoji, priority))
            
            if len(found) >= max_count:
                break
    
    return [emoji for emoji, _ in found]


def detect_price_change_emoji(line):
    """Определяет эмодзи для изменения цены"""
    if any(indicator in line for indicator in ['+', 'up', '↑']):
        return "🟢"
    elif any(indicator in line for indicator in ['-', 'down', '↓']):
        return "🔴"
    return "•"


# ========================================
# ФОРМАТИРОВАНИЕ TELEGRAM
# ========================================

def format_telegram_improved(title, text, hashtags):
    """Улучшенное форматирование для Telegram"""
    start_time = time.time()
    
    try:
        title = safe_str(title, "Crypto Update", 100)
        text = safe_str(text, "", MAX_TEXT_LENGTH)
        hashtags = safe_str(hashtags, "", 200)
        
        if not text:
            logger.warning("⚠️ Пустой текст после санитизации")
            return f"<b>{title}</b>\n\n{hashtags}"
        
        emoji = TITLE_EMOJI_MAP.get(title, "📰")
        header = f"{emoji} <b>{title}</b>"
        
        lines = text.split('\n')
        processed = []
        line_count = 0
        
        for line in lines:
            if line_count >= MAX_LINE_COUNT:
                logger.warning(f"⚠️ Достигнут лимит строк ({MAX_LINE_COUNT})")
                break
            
            line = line.strip()
            if not line:
                continue
            
            line_count += 1
            
            if CRYPTO_PRICE_PATTERN.match(line):
                price_emoji = detect_price_change_emoji(line)
                processed.append(f"{price_emoji} {line}")
            elif LIST_ITEM_PATTERN.match(line):
                clean = LIST_ITEM_PATTERN.sub('', line)
                processed.append(f"• {clean}")
            elif line.endswith((':','–','—')) and len(line) < 50:
                processed.append(f"<b>{line}</b>")
            else:
                processed.append(line)
        
        formatted = '\n\n'.join(processed)
        message = f"{header}\n\n{formatted}"
        
        if hashtags:
            message += f"\n\n{hashtags}"
        
        if len(message) > MAX_TELEGRAM_LENGTH:
            logger.warning(f"⚠️ Сообщение слишком длинное ({len(message)}), обрезаю")
            message = message[:MAX_TELEGRAM_LENGTH-3] + "..."
        
        duration = time.time() - start_time
        if duration > 0.5:
            logger.warning(f"⚠️ Медленное форматирование TG: {duration:.2f}s")
        
        return message
        
    except Exception as e:
        logger.error(f"✗ Ошибка в format_telegram_improved: {e}")
        return f"<b>{safe_str(title, 'Update')}</b>\n\n{safe_str(text, 'No content')[:500]}"


# ========================================
# ФОРМАТИРОВАНИЕ TWITTER
# ========================================

def extract_bullet_points(text):
    """Извлекает пункты списка из текста"""
    points = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if LIST_ITEM_PATTERN.match(line) or CRYPTO_PRICE_PATTERN.match(line):
            clean = LIST_ITEM_PATTERN.sub('', line).strip()
            if clean and len(clean) > 10:
                points.append(clean)
    
    return points


def extract_intro_sentence(text):
    """Извлекает первое предложение для intro"""
    match = re.match(r'^([^.!?]+[.!?])', text)
    if match:
        intro = match.group(1).strip()
        if get_twitter_length(intro) <= 200:
            return intro
    
    if len(text) > 200:
        return text[:197] + "..."
    return text


def format_twitter_thread(title, text, hashtags):
    """
    Создаёт мини-тред для Twitter (оптимизировано для Free tier)
    v3.1.2: Показывает 2-3 ключевых пункта вместо одного
    Возвращает: list of str или None
    """
    try:
        tweets = []
        
        title = safe_str(title, "Update", 50)
        text = safe_str(text, "", MAX_TEXT_LENGTH)
        hashtags = safe_str(hashtags, "", 150)
        
        if not text:
            logger.warning("⚠️ Пустой текст для треда")
            return None
        
        emoji = TITLE_EMOJI_MAP.get(title, "📰")
        context_emojis = get_context_emojis(text, max_count=2)
        
        # Твит 1: INTRO
        intro = extract_intro_sentence(text)
        context_str = " ".join(context_emojis) if context_emojis else ""
        
        tweet1 = f"{emoji} {title}"
        if context_str:
            tweet1 += f" {context_str}"
        tweet1 += f"\n\n{intro}\n\n🧵👇"
        
        if get_twitter_length(tweet1) > MAX_TWITTER_LENGTH:
            max_intro = MAX_TWITTER_LENGTH - get_twitter_length(f"{emoji} {title} {context_str}\n\n\n\n🧵👇") - 5
            intro = text[:max_intro-3] + "..."
            tweet1 = f"{emoji} {title}"
            if context_str:
                tweet1 += f" {context_str}"
            tweet1 += f"\n\n{intro}\n\n🧵👇"
        
        tweets.append(tweet1)
        
        # Твит 2: 2-3 ГЛАВНЫХ ПУНКТА (NEW в v3.1.2)
        points = extract_bullet_points(text)
        
        if not points:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            points = [s.strip() for s in sentences if len(s.strip()) > 20][:3]
        
        if not points or len(points) < 1:
            logger.warning("⚠️ Недостаточно контента для треда, используем одиночный твит")
            return None
        
        # Берём 2-3 главных пункта (было: только 1)
        key_points = points[:3]  # Первые 3 пункта
        tweet2_lines = []
        
        for point in key_points:
            if CRYPTO_PRICE_PATTERN.match(point):
                price_emoji = detect_price_change_emoji(point)
                line = f"{price_emoji} {point}"
            else:
                line = f"• {point}"
            
            # Сокращаем длинные пункты для экономии места
            if len(line) > 100:
                line = line[:97] + "..."
            
            tweet2_lines.append(line)
        
        tweet2 = "\n\n".join(tweet2_lines)
        
        # Проверяем что влезает в лимит Twitter
        if get_twitter_length(tweet2) > MAX_TWITTER_LENGTH:
            # Если не влезает 3 пункта - берём только 2
            logger.info("  ℹ️  3 пункта не влезают, используем 2")
            tweet2_lines = tweet2_lines[:2]
            tweet2 = "\n\n".join(tweet2_lines)
            
            # Если всё равно не влезает - берём только 1
            if get_twitter_length(tweet2) > MAX_TWITTER_LENGTH:
                logger.info("  ℹ️  2 пункта не влезают, используем 1")
                tweet2 = tweet2_lines[0]
                if get_twitter_length(tweet2) > MAX_TWITTER_LENGTH:
                    tweet2 = tweet2[:MAX_TWITTER_LENGTH-3] + "..."
        
        tweets.append(tweet2)
        logger.info(f"  ✓ Твит 2 содержит {len(tweet2_lines)} пункта(ов)")
        
        # Твит 3: ХЭШТЕГИ
        if hashtags:
            tweets.append(hashtags)
        
        if len(tweets) < 2:
            logger.warning("⚠️ Тред слишком короткий")
            return None
        
        logger.info(f"✓ Создан тред из {len(tweets)} твитов")
        return tweets
        
    except Exception as e:
        logger.error(f"✗ Ошибка создания треда: {e}")
        return None


def format_twitter_single(title, text, hashtags, max_len=270):
    """Одиночный сокращенный твит"""
    try:
        title = safe_str(title, "Update", 50)
        text = safe_str(text, "", 2000)
        hashtags = safe_str(hashtags, "", 150)
        
        if not text:
            return f"{title}\n\n{hashtags}"
        
        emoji = TITLE_EMOJI_MAP.get(title, "📰")
        context_emojis = get_context_emojis(text, max_count=1)
        
        if context_emojis:
            header = f"{emoji} {title} {context_emojis[0]}"
        else:
            header = f"{emoji} {title}"
        
        reserved = get_twitter_length(header) + get_twitter_length(hashtags) + 6
        available = max_len - reserved
        
        if available < MIN_TWITTER_SPACE:
            tags_list = hashtags.split()[:2]
            hashtags = " ".join(tags_list) if tags_list else ""
            reserved = get_twitter_length(header) + get_twitter_length(hashtags) + 6
            available = max_len - reserved
        
        short_text = extract_short_text_safe(text, available)
        tweet = f"{header}\n\n{short_text}\n\n{hashtags}"
        
        if get_twitter_length(tweet) > MAX_TWITTER_LENGTH:
            tweet = tweet[:277] + "..."
        
        return tweet
        
    except Exception as e:
        logger.error(f"✗ Ошибка в format_twitter_single: {e}")
        return f"{title}\n\nCheck Telegram"


def extract_short_text_safe(text, max_length):
    """Безопасное извлечение короткого текста"""
    if not text or max_length < 10:
        return ""
    
    text = text.strip()
    if get_twitter_length(text) <= max_length:
        return text
    
    result = []
    current = ""
    char_count = 0
    max_chars = min(len(text), max_length * 2)
    
    for char in text[:max_chars]:
        current += char
        char_count += 1
        
        if char in '.!?' and char_count > 20:
            if get_twitter_length(current) <= max_length:
                result.append(current.strip())
                current = ""
            else:
                break
        
        if len(result) >= 3:
            break
    
    if result:
        final = " ".join(result)
        if get_twitter_length(final) <= max_length:
            return final
    
    return text[:max_length-3] + "..."


# ========================================
# ГЛАВНАЯ ФУНКЦИЯ
# ========================================

def send_improved(question, answer, 
                 extract_tldr_fn, clean_text_fn, config_dict,
                 get_image_fn, send_tg_photo_fn, send_tg_msg_fn,
                 send_twitter_thread_fn, twitter_enabled, twitter_keys):
    """
    Главная функция для отправки контента
    
    v3.1.2: Показ 2-3 пунктов в Twitter тредах
    v3.1.1: Оптимизация для Twitter Free tier
    """
    total_start = time.time()
    
    try:
        logger.info(f"\n📝 Форматирование v{__version__}")
        logger.info(f"🐦 Twitter режим: {TWITTER_MODE}")
        
        # 1-2. Извлекаем и очищаем
        tldr_text = extract_tldr_fn(answer)
        if not tldr_text:
            logger.error("✗ Пустой TLDR")
            return False
        
        tldr_text = clean_text_fn(question, tldr_text)
        if not tldr_text:
            logger.error("✗ Пустой текст после очистки")
            return False
        
        # 3. Конфигурация
        config = config_dict.get(question, {
            "title": "Crypto Update",
            "hashtags": "#Crypto #Bitcoin"
        })
        
        title = config.get("title", "Crypto Update")
        hashtags = config.get("hashtags", "#Crypto")
        
        logger.info(f"  Заголовок: {title}")
        logger.info(f"  Длина: {len(tldr_text)}")
        
        # 4. Форматируем Telegram
        try:
            tg_message = format_telegram_improved(title, tldr_text, hashtags)
            logger.info(f"  ✓ Telegram: {len(tg_message)} символов")
        except Exception as e:
            logger.error(f"  ✗ Ошибка TG: {e}")
            tg_message = f"<b>{title}</b>\n\n{tldr_text[:500]}\n\n{hashtags}"
        
        # 5. Картинка
        image_url = None
        try:
            image_url = get_image_fn()
        except Exception as e:
            logger.warning(f"  ⚠️ Нет картинки: {e}")
        
        # 6. Отправляем Telegram
        logger.info("\n📤 Отправка Telegram...")
        tg_success = False
        
        try:
            if image_url:
                tg_success = send_tg_photo_fn(image_url, tg_message)
            else:
                tg_success = send_tg_msg_fn(tg_message)
        except Exception as e:
            logger.error(f"  ✗ Ошибка: {e}")
        
        time.sleep(2)
        
        # 7. Twitter
        tw_status = "Отключен"
        
        if twitter_enabled and all(twitter_keys):
            try:
                logger.info("\n🐦 Подготовка Twitter...")
                
                twitter_content = {
                    "title": title,
                    "text": tldr_text,
                    "hashtags": hashtags,
                    "mode": TWITTER_MODE
                }
                
                if TWITTER_MODE == "thread":
                    tweets = format_twitter_thread(title, tldr_text, hashtags)
                    
                    if tweets and len(tweets) >= 2:
                        twitter_content["tweets"] = tweets
                        logger.info(f"  ✓ Twitter тред: {len(tweets)} твитов")
                    else:
                        logger.warning("  ⚠️ Fallback на одиночный твит")
                        twitter_content["mode"] = "single"
                        twitter_content["tweet"] = format_twitter_single(title, tldr_text, hashtags)
                else:
                    twitter_content["tweet"] = format_twitter_single(title, tldr_text, hashtags)
                    logger.info(f"  ✓ Twitter: {get_twitter_length(twitter_content['tweet'])} символов")
                
                tw_success = send_twitter_thread_fn(twitter_content, image_url)
                tw_status = f"✓ Успешно ({twitter_content['mode']})" if tw_success else "✗ Ошибка"
                
            except Exception as e:
                logger.error(f"  ✗ Twitter: {e}")
                import traceback
                traceback.print_exc()
                tw_status = "✗ Ошибка"
        
        # 8. Итоги
        total_duration = time.time() - total_start
        logger.info(f"\n📊 РЕЗУЛЬТАТЫ:")
        logger.info(f"  Telegram: {'✓' if tg_success else '✗'}")
        logger.info(f"  Twitter: {tw_status}")
        logger.info(f"  Время: {total_duration:.2f}s\n")
        
        return tg_success
        
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
