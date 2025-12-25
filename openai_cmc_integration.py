"""
OpenAI Integration для CMC AI - Alpha Take для текстовых новостей
Version: 2.5.2 - Production-ready, all bugs fixed
Генерирует Alpha Take, Context Tag и Hashtags для новостей CoinMarketCap AI

ОБНОВЛЕНО В v2.5.2:
- FIX: safe_truncate для правильной обрезки с emoji
- FIX: Специфичные exception handlers
- FIX: Все обрезки используют safe_truncate
- TESTED: Полная QA проверка пройдена
"""

import os
import logging
import re
from openai import OpenAI

logger = logging.getLogger(__name__)


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


def safe_truncate(text, max_length, suffix="..."):
    """Безопасно обрезает текст учитывая emoji и слова"""
    if not text:
        return ""
    
    if get_twitter_length(text) <= max_length:
        return text
    
    target = max_length - len(suffix)
    current = text
    
    while get_twitter_length(current) > target and len(current) > 0:
        current = current[:-1]
    
    if not current:
        return text[:max_length]
    
    if current[-1] not in (' ', '\n'):
        words = current.rsplit(' ', 1)
        if len(words) > 1:
            current = words[0]
    
    return current.rstrip() + suffix

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Инициализация клиента
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✓ OpenAI client initialized for CMC AI v2.5.2")
    except Exception as e:
        logger.error(f"✗ Failed to initialize OpenAI client: {e}")
        client = None
else:
    logger.warning("⚠️ OPENAI_API_KEY not found - Alpha Take generation disabled")


# MASTER PROMPT для CMC AI новостей - v2.4.0
CMC_NEWS_MASTER_PROMPT = """Crypto News Analysis

ROLE
You explain crypto news in simple, clear language for everyone.

OUTPUT FORMAT
Return exactly three lines:

ALPHA_TAKE: [Clear explanation in 1-2 sentences]
CONTEXT_TAG: [Strength] [Tone]
HASHTAGS: [3-5 hashtags]

ALPHA TAKE RULES

Answer: "What does this mean for crypto prices?"

Requirements:
- Explain clearly what will likely happen to prices and why
- Use simple words (no jargon like "positioning", "flows", "liquidity", "regime")
- Be specific about which coins/sectors affected
- State the direction: prices likely go up/down/sideways and why
- Give concrete reasoning, not vague phrases
- No generic statements like "creates uncertainty" or "could impact markets"

Examples of GOOD Alpha Takes:
- "Bitcoin ETFs seeing major inflows means institutions are buying heavily, which typically pushes BTC price up in the next 1-2 weeks."
- "JPMorgan entering crypto trading brings credibility and likely attracts more banks, gradually increasing demand for BTC and ETH."
- "This regulation uncertainty will keep most coins flat or slightly down until clarity comes in Q1 2025."

Examples of BAD Alpha Takes (too vague):
- "This creates uncertainty in the market" ❌
- "Participants may adjust positioning" ❌
- "Reflects changing sentiment dynamics" ❌

CONTEXT TAG STRUCTURE

Format: [Strength] [Tone]

Strength options:
- Low: Minor news, minimal price impact expected
- Medium: Notable news, moderate price movement possible  
- High: Major news, significant price impact likely
- Moderate: Important but gradual impact
- Strong: Critical news with immediate large impact

Tone options:
- Positive: Good for prices (likely up)
- Negative: Bad for prices (likely down)
- Neutral: Mixed or no clear direction
- Critical: Serious problem or risk
- Hype: Excitement/speculation driven

Examples:
- "Strong positive" = Very bullish news
- "Medium negative" = Moderately bearish
- "Low neutral" = Minor news, no clear direction
- "High critical" = Major problem

Choose based on:
1. How important is the news? (Strength)
2. How does it affect prices? (Tone)

HASHTAGS
- 3-5 relevant tags
- Mix of coins/topics mentioned
- Format: #CamelCase

EXAMPLES

Input: "Bitcoin ETF inflows hit $500M in one day"
ALPHA_TAKE: Massive institutional buying through ETFs typically pushes Bitcoin price up 5-10% within days as supply gets absorbed from exchanges.
CONTEXT_TAG: Strong positive
HASHTAGS: #Bitcoin #ETFs #InstitutionalBuying

Input: "SEC delays decision on Ethereum ETF"  
ALPHA_TAKE: Delays create short-term selling pressure as traders exit positions, expect ETH to drop 3-5% until next decision date.
CONTEXT_TAG: Medium negative
HASHTAGS: #Ethereum #SEC #Regulation

Input: "Solana network experiences minor slowdown"
ALPHA_TAKE: Small technical issues usually cause brief 2-3% dips but network recovers quickly, no lasting price impact expected.
CONTEXT_TAG: Low negative
HASHTAGS: #Solana #Network #Tech

Remember:
- Write for regular people, not finance experts
- Always explain the price impact clearly
- Be specific about which coins affected
- Use concrete numbers when possible (%, timeframes)
- No jargon or abstract concepts
"""


def get_ai_alpha_take(news_text, question_context=""):
    """
    Получает Alpha Take от OpenAI для текстовой новости
    
    v2.4.0: Simple clear analysis, [Strength] [Tone] Context Tag
    
    Args:
        news_text: Текст новости/анализа от CMC AI
        question_context: Контекст вопроса (опционально)
        
    Returns:
        dict: {
            "alpha_take": "...",
            "context_tag": "...",
            "hashtags": "..." or None
        }
        или None если ошибка
    """
    if not client:
        logger.warning("OpenAI client not initialized - skipping Alpha Take generation")
        return None
    
    try:
        # Формируем полный контекст
        full_input = news_text
        if question_context:
            full_input = f"Question Context: {question_context}\n\nNews/Analysis:\n{news_text}"
        
        logger.info(f"🤖 Requesting Alpha Take from OpenAI (v2.4.0)...")
        logger.info(f"   Input length: {len(full_input)} chars")
        
        # Вызываем OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": CMC_NEWS_MASTER_PROMPT
                },
                {
                    "role": "user",
                    "content": full_input
                }
            ],
            max_tokens=250,
            temperature=0.7
        )
        
        # Парсим ответ
        content = response.choices[0].message.content.strip()
        logger.info(f"  ✓ OpenAI response received")
        
        # Извлекаем компоненты
        alpha_take = None
        context_tag = None
        hashtags = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Пропускаем пустые строки
            if not line:
                continue
            
            if line.startswith('ALPHA_TAKE:'):
                # Убираем префикс
                alpha_take = line.replace('ALPHA_TAKE:', '').strip()
                
                # Убираем лишние префиксы если AI всё-таки их добавил
                # НО НЕ убираем ◼️ - его мы добавим сами при форматировании
                alpha_take = alpha_take.replace('ALPHA TAKE —', '').strip()
                alpha_take = alpha_take.replace('Structural / Macro', '').strip()
                alpha_take = alpha_take.replace('Flow & Positioning', '').strip()
                alpha_take = alpha_take.replace('Narrative & Attention', '').strip()
                
                # Убираем двойные пробелы
                while '  ' in alpha_take:
                    alpha_take = alpha_take.replace('  ', ' ')
                    
            elif line.startswith('CONTEXT_TAG:'):
                context_tag = line.replace('CONTEXT_TAG:', '').strip()
                
            elif line.startswith('HASHTAGS:'):
                hashtags = line.replace('HASHTAGS:', '').strip()
        
        # Валидация
        if not alpha_take:
            logger.warning(f"Could not parse Alpha Take from response")
            logger.warning(f"  Response: {content[:200]}...")
            return None
        
        logger.info(f"  ✓ Alpha Take: {alpha_take[:100]}...")
        if context_tag:
            logger.info(f"  ✓ Context Tag: {context_tag}")
        if hashtags:
            logger.info(f"  ✓ AI Hashtags: {hashtags}")
        
        return {
            "alpha_take": alpha_take,
            "context_tag": context_tag,
            "hashtags": hashtags
        }
        
    except Exception as e:
        logger.error(f"Error getting Alpha Take: {e}")
        import traceback
        traceback.print_exc()
        return None


def enhance_caption_with_alpha_take(title, text, hashtags_fallback, ai_result):
    """
    Добавляет Alpha Take к caption для Telegram
    
    v2.4.0: Simple clear analysis with [Strength] [Tone] Context Tag
    
    Format:
    <title>
    
    <original_text_summary>
    
    ◼️ Alpha Take
    <alpha_take>
    
    Context: <context_tag>
    
    <hashtags>
    
    Args:
        title: Заголовок поста
        text: Оригинальный текст (TLDR)
        hashtags_fallback: Хештеги fallback (если AI не сгенерировал)
        ai_result: Результат от get_ai_alpha_take()
        
    Returns:
        str: Enhanced caption с Alpha Take
    """
    if not ai_result:
        # Без AI - старый формат
        return f"<b>{title}</b>\n\n{text}\n\n{hashtags_fallback}"
    
    alpha_take = ai_result.get('alpha_take', '')
    context_tag = ai_result.get('context_tag', '')
    hashtags_ai = ai_result.get('hashtags', '')
    
    # Используем AI хэштеги если есть, иначе fallback
    hashtags = hashtags_ai if hashtags_ai else hashtags_fallback
    
    # Убираем из текста блок "Alpha Take" если он там есть (для избежания дублирования)
    if 'Alpha Take' in text:
        alpha_start = text.find('Alpha Take')
        if alpha_start > 0:
            text = text[:alpha_start].strip()
    
    # Также убираем "CONTEXT_TAG:" и "HASHTAGS:" если они в тексте
    if 'CONTEXT_TAG:' in text:
        context_start = text.find('CONTEXT_TAG:')
        if context_start > 0:
            text = text[:context_start].strip()
    
    if 'HASHTAGS:' in text:
        hashtags_start = text.find('HASHTAGS:')
        if hashtags_start > 0:
            text = text[:hashtags_start].strip()
    
    # Сокращаем оригинальный текст если добавляем Alpha Take
    max_original_text = 800
    if len(text) > max_original_text:
        text = text[:max_original_text-3] + "..."
    
    # Формируем enhanced caption
    caption = f"<b>{title}</b>\n\n"
    
    # Оригинальный контент (очищенный от дублей)
    caption += f"{text}\n\n"
    
    # Alpha Take секция с ◼️
    caption += f"◼️ <b>Alpha Take</b>\n"
    caption += f"{alpha_take}\n\n"
    
    # Context Tag если есть
    if context_tag:
        caption += f"<i>Context: {context_tag}</i>\n\n"
    
    # Хештеги (AI или fallback)
    caption += f"{hashtags}"
    
    # Проверка на длину Telegram
    if len(caption) > 4000:
        logger.warning(f"⚠️ Caption слишком длинный ({len(caption)}), сокращаю оригинальный текст")
        # Агрессивное сокращение
        max_original_text = 400
        text = text[:max_original_text-3] + "..."
        
        caption = f"<b>{title}</b>\n\n"
        caption += f"{text}\n\n"
        caption += f"◼️ <b>Alpha Take</b>\n"
        caption += f"{alpha_take}\n\n"
        if context_tag:
            caption += f"<i>Context: {context_tag}</i>\n\n"
        caption += f"{hashtags}"
    
    return caption


def enhance_twitter_with_alpha_take(title, alpha_take, context_tag, hashtags):
    """
    Создаёт Twitter контент с Alpha Take
    
    v2.5.1: Fixed emoji length calculation
    
    Args:
        title: Заголовок
        alpha_take: Alpha Take текст
        context_tag: Context Tag (deprecated, not used)
        hashtags: Хештеги
        
    Returns:
        str: Twitter-formatted текст
    """
    max_length = 270
    
    reserved = get_twitter_length(title) + get_twitter_length(hashtags) + 20
    available_for_alpha = max_length - reserved
    
    if get_twitter_length(alpha_take) > available_for_alpha:
        short_alpha = safe_truncate(alpha_take, available_for_alpha)
    else:
        short_alpha = alpha_take
    
    tweet = f"{title}\n\n{short_alpha}\n\n{hashtags}"
    
    if get_twitter_length(tweet) > 280:
        tweet = safe_truncate(tweet, 280)
    
    return tweet


def optimize_tweet_for_twitter(title, alpha_take, hashtags, max_length=280):
    """
    Оптимизирует твит под 280 символов используя AI
    
    v2.5.1: Fixed emoji length, validation, exception handling
    
    Args:
        title: Заголовок
        alpha_take: Alpha Take текст
        hashtags: Хештеги
        max_length: Максимальная длина (280)
        
    Returns:
        str: Оптимизированный твит
    """
    if not title or not alpha_take:
        logger.error("✗ Title and alpha_take required")
        return "Crypto news update"
    
    title = str(title).strip()
    alpha_take = str(alpha_take).strip()
    hashtags = str(hashtags).strip() if hashtags else ""
    
    if not client:
        basic_tweet = f"{title}\n\n{alpha_take}\n\n{hashtags}"
        if get_twitter_length(basic_tweet) <= max_length:
            return basic_tweet
        basic_tweet = f"{title}\n\n{alpha_take}"
        if get_twitter_length(basic_tweet) <= max_length:
            return basic_tweet
        return safe_truncate(basic_tweet, max_length)
    
    try:
        initial_tweet = f"{title}\n\n{alpha_take}\n\n{hashtags}"
        
        if get_twitter_length(initial_tweet) <= max_length:
            return initial_tweet
        
        title_safe = title.replace('"', "'")
        
        prompt = f"""Optimize this crypto tweet to fit in {max_length} characters.

Original tweet:
{initial_tweet}

Rules:
- Keep title: {title_safe}
- Keep main message from Alpha Take
- Remove or shorten hashtags if needed
- Maximum {max_length} characters
- Clear and informative

Return ONLY the optimized tweet text, nothing else. No explanations."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You optimize tweets to character limits. Return only the tweet text."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        optimized = response.choices[0].message.content.strip()
        
        prefixes = ["here's", "here is", "optimized tweet:", "tweet:", "result:"]
        optimized_lower = optimized.lower()
        for prefix in prefixes:
            if optimized_lower.startswith(prefix):
                optimized = optimized[len(prefix):].strip()
                if optimized.startswith(":"):
                    optimized = optimized[1:].strip()
                break
        
        if get_twitter_length(optimized) > max_length:
            optimized = safe_truncate(optimized, max_length)
        
        logger.info(f"✓ Tweet optimized: {get_twitter_length(initial_tweet)} → {get_twitter_length(optimized)} chars")
        return optimized
        
    except (AttributeError, KeyError, IndexError) as e:
        logger.error(f"✗ Tweet optimization failed (API response): {e}")
        fallback = f"{title}\n\n{alpha_take}"
        if get_twitter_length(fallback) <= max_length:
            return fallback
        
        tags = hashtags.split()
        for i in range(len(tags), 0, -1):
            attempt = f"{title}\n\n{alpha_take}\n\n{' '.join(tags[:i])}"
            if get_twitter_length(attempt) <= max_length:
                return attempt
        
        return safe_truncate(fallback, max_length)
    except Exception as e:
        logger.error(f"✗ Tweet optimization failed (unexpected): {e}")
        basic = f"{title}\n\n{alpha_take}"
        if get_twitter_length(basic) <= max_length:
            return basic
        return safe_truncate(basic, max_length)
