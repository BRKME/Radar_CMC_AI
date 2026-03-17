"""
formatting.py - Модуль улучшенного форматирования для Telegram и Twitter
Version: 3.3.0
Senior QA Approved - Production Ready

ОБНОВЛЕНО В v3.3.0:
- Импорт get_twitter_length из utils.py (унификация)
- Удалена локальная копия функции

ОБНОВЛЕНО В v3.2.1:
- FIX: Alpha Take теперь попадает в Telegram!
- Используем enhance_caption_with_alpha_take для Telegram caption

ОБНОВЛЕНО В v3.2.0:
- Twitter треды теперь включают Alpha Take!
- Последний твит: Alpha Take + Context Tag + Хэштеги
- Полные информативные треды (не урезанные)
- Формат: Intro → Events → Alpha Take

ОБНОВЛЕНО В v3.1.2:
- Twitter треды показывают 2-3 ключевых пункта (было: только 1)
- Умная разбивка контента на твиты

ОБНОВЛЕНО В v3.1.1:
- Оптимизация для Twitter Free tier
- Мини-треды: максимум 3-5 твитов
- Увеличена пауза между твитами: 15 секунд
"""

import re
import time
import logging

# Импорт общих утилит
from utils import get_twitter_length, safe_truncate

logger = logging.getLogger(__name__)

# ========================================
# ВЕРСИЯ И НАСТРОЙКИ
# ========================================

__version__ = "3.3.0"

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
MAX_THREAD_TWEETS = 5  # Увеличено для Alpha Take (было 3)

# Пауза между твитами
TWEET_DELAY = 15  # секунды

# Эмодзи для заголовков
TITLE_EMOJI_MAP = {
    "Crypto Insights": "💡",
    "Market Analysis": "📊",
    "Daily Market Sentiment": "🎭",
    "Upcoming Crypto Events": "📅",
    "Bullish Crypto Watchlist": "🚀",
    "Trending Crypto Narratives": "🔥"
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

# get_twitter_length импортируется из utils.py

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


# get_twitter_length теперь импортируется из utils.py (v3.3.0)


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
        
        # Пропускаем Alpha Take и Context Tag
        if line.startswith('Alpha Take') or line.startswith('Context:'):
            continue
        
        if LIST_ITEM_PATTERN.match(line) or CRYPTO_PRICE_PATTERN.match(line):
            clean = LIST_ITEM_PATTERN.sub('', line).strip()
            if clean and len(clean) > 10:
                points.append(clean)
    
    return points


def extract_intro_sentence(text):
    """Извлекает первое предложение для intro"""
    # Пропускаем Alpha Take если он в начале
    lines = text.split('\n')
    clean_text = []
    skip_alpha = False
    
    for line in lines:
        if 'Alpha Take' in line:
            skip_alpha = True
            continue
        if skip_alpha and (line.startswith('Context:') or not line.strip()):
            continue
        if line.strip():
            clean_text.append(line)
            break
    
    if not clean_text:
        return text[:100]
    
    first_line = clean_text[0]
    match = re.match(r'^([^.!?]+[.!?])', first_line)
    if match:
        intro = match.group(1).strip()
        if get_twitter_length(intro) <= 200:
            return intro
    
    if len(first_line) > 200:
        return first_line[:197] + "..."
    return first_line


def format_twitter_thread(title, text, hashtags, alpha_take=None, context_tag=None):
    """
    Создаёт полный тред для Twitter с Alpha Take
    
    v3.2.0: Включает Alpha Take в последний твит!
    
    Формат:
    Твит 1: Заголовок + intro
    Твит 2-N: События/пункты (2-3 на твит)
    Последний твит: Alpha Take + Context Tag + Хэштеги
    
    Args:
        title: Заголовок
        text: Текст (без Alpha Take)
        hashtags: Хэштеги
        alpha_take: Alpha Take текст (опционально)
        context_tag: Context Tag (опционально)
    
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
        
        # ТВИТ 1: INTRO
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
        
        # ТВИТЫ 2-N: СОБЫТИЯ/ПУНКТЫ
        points = extract_bullet_points(text)
        
        if not points:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            points = [s.strip() for s in sentences if len(s.strip()) > 20][:5]
        
        if points and len(points) >= 1:
            # Группируем пункты по твитам (2-3 на твит)
            i = 0
            while i < len(points) and len(tweets) < (MAX_THREAD_TWEETS - 1):  # -1 для Alpha Take
                batch = []
                batch_length = 0
                
                # Берем 2-3 пункта пока влезает
                while i < len(points) and len(batch) < 3:
                    point = points[i]
                    
                    # Форматируем пункт
                    if CRYPTO_PRICE_PATTERN.match(point):
                        price_emoji = detect_price_change_emoji(point)
                        formatted = f"{price_emoji} {point}"
                    else:
                        formatted = f"• {point}"
                    
                    # Сокращаем длинные пункты
                    if len(formatted) > 100:
                        formatted = formatted[:97] + "..."
                    
                    # Проверяем влезет ли
                    test_text = "\n\n".join(batch + [formatted])
                    if get_twitter_length(test_text) > MAX_TWITTER_LENGTH:
                        if len(batch) == 0:
                            # Даже один пункт не влезает - берем укороченный
                            batch.append(formatted[:MAX_TWITTER_LENGTH-10] + "...")
                            i += 1
                        break
                    
                    batch.append(formatted)
                    i += 1
                
                if batch:
                    tweets.append("\n\n".join(batch))
        
        # ПОСЛЕДНИЙ ТВИТ: ALPHA TAKE + CONTEXT TAG + ХЭШТЕГИ
        if alpha_take:
            final_tweet = f"◼ Alpha Take\n\n{alpha_take}"
            
            if context_tag:
                final_tweet += f"\n\nContext: {context_tag}"
            
            final_tweet += f"\n\n{hashtags}"
            
            # Проверяем длину
            if get_twitter_length(final_tweet) > MAX_TWITTER_LENGTH:
                # Сокращаем Alpha Take
                max_alpha = MAX_TWITTER_LENGTH - get_twitter_length(f"◼ Alpha Take\n\n\n\nContext: {context_tag}\n\n{hashtags}") - 10
                short_alpha = alpha_take[:max_alpha-3] + "..."
                final_tweet = f"◼ Alpha Take\n\n{short_alpha}"
                if context_tag:
                    final_tweet += f"\n\nContext: {context_tag}"
                final_tweet += f"\n\n{hashtags}"
            
            tweets.append(final_tweet)
        else:
            # Без Alpha Take - просто хэштеги
            if hashtags:
                tweets.append(hashtags)
        
        if len(tweets) < 2:
            logger.warning("⚠️ Тред слишком короткий")
            return None
        
        logger.info(f"✓ Создан тред из {len(tweets)} твитов (включая Alpha Take)")
        return tweets
        
    except Exception as e:
        logger.error(f"✗ Ошибка создания треда: {e}")
        import traceback
        traceback.print_exc()
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
                 send_twitter_thread_fn, twitter_enabled, twitter_keys,
                 alpha_take=None, context_tag=None):
    """
    Главная функция для отправки контента
    
    v3.2.1: Alpha Take теперь попадает в Telegram!
    v3.2.0: Добавлены alpha_take и context_tag для полных тредов
    
    Args:
        ... (стандартные параметры)
        alpha_take: Alpha Take текст (опционально)
        context_tag: Context Tag (опционально)
    """
    total_start = time.time()
    
    try:
        logger.info(f"\n📝 Форматирование v{__version__}")
        logger.info(f"🐦 Twitter режим: {TWITTER_MODE}")
        if alpha_take:
            logger.info(f"  ✓ Alpha Take доступен для Twitter треда")
        
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
            # v3.2.1: Используем Alpha Take для Telegram если доступен
            if alpha_take and context_tag:
                # Импортируем функцию для Alpha Take
                from openai_cmc_integration import enhance_caption_with_alpha_take
                
                # Формируем ai_result для enhance_caption_with_alpha_take
                ai_result = {
                    'alpha_take': alpha_take,
                    'context_tag': context_tag,
                    'hashtags': None  # Будет использован hashtags из config
                }
                
                tg_message = enhance_caption_with_alpha_take(
                    title=title,
                    text=tldr_text,
                    hashtags_fallback=hashtags,
                    ai_result=ai_result
                )
                logger.info(f"  ✓ Telegram (с Alpha Take): {len(tg_message)} символов")
            else:
                # Без Alpha Take - обычный формат
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
                    "mode": TWITTER_MODE,
                    "alpha_take": alpha_take,  # v3.2.0: Передаем Alpha Take
                    "context_tag": context_tag  # v3.2.0: Передаем Context Tag
                }
                
                if TWITTER_MODE == "thread":
                    tweets = format_twitter_thread(
                        title, tldr_text, hashtags,
                        alpha_take=alpha_take,  # v3.2.0
                        context_tag=context_tag  # v3.2.0
                    )
                    
                    if tweets and len(tweets) >= 2:
                        twitter_content["tweets"] = tweets
                        logger.info(f"  ✓ Twitter тред: {len(tweets)} твитов (с Alpha Take)")
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
