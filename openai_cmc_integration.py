"""
OpenAI Integration для CMC AI - Alpha Take для текстовых новостей
Version: 3.0.0 - Actionable insights, not summaries
Генерирует Alpha Take, Context Tag и Hashtags для новостей CoinMarketCap AI

ОБНОВЛЕНО В v3.0.0:
- Полностью переписан промпт для ИНСАЙТОВ вместо пересказа
- Формула: [Наблюдение] + [Исторический контекст] + [Ожидаемый результат]
- Примеры с конкретными числами и таймингами
- Антипаттерны: "creates uncertainty", "may impact prices"

ОБНОВЛЕНО В v2.7.0:
- Хэштеги теперь вверху caption
- Максимум 2 хэштега
- Фильтрация длинных хэштегов (>10 символов)
"""

import os
import logging
import re
from openai import OpenAI

# Импорт общих утилит
from utils import get_twitter_length, safe_truncate, sanitize_hashtags

logger = logging.getLogger(__name__)

# get_twitter_length и safe_truncate импортируются из utils.py

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Инициализация клиента
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✓ OpenAI client initialized for CMC AI v3.0.0")
    except Exception as e:
        logger.error(f"✗ Failed to initialize OpenAI client: {e}")
        client = None
else:
    logger.warning("⚠️ OPENAI_API_KEY not found - Alpha Take generation disabled")


# MASTER PROMPT для CMC AI новостей - v3.0.0
CMC_NEWS_MASTER_PROMPT = """You are a crypto trading analyst providing actionable insights.

OUTPUT FORMAT
Return exactly three lines:

ALPHA_TAKE: [1-2 sentences of ACTIONABLE insight]
CONTEXT_TAG: [Strength] [Tone]
HASHTAGS: [2 short hashtags]

═══════════════════════════════════════════════════════════
ALPHA TAKE RULES — THIS IS CRITICAL
═══════════════════════════════════════════════════════════

Your job is NOT to summarize or rephrase the news.
Your job IS to provide INSIGHT that the reader couldn't figure out themselves.

Ask yourself: "What would a professional trader notice that a regular person would miss?"

GOOD Alpha Takes include:
• Historical pattern: "Last 3 times ETF inflows exceeded $400M, BTC rallied 12% within 10 days"
• Hidden signal: "Whale wallets moved 15K BTC to exchanges — historically precedes 5-8% drops"
• Timing insight: "Options expiry Friday likely amplifies this move, watch for reversal Monday"
• Contrarian view: "Despite bearish headlines, on-chain data shows accumulation — smart money buying"
• Specific target: "Key resistance at $68K — break above likely triggers $72K run"
• Risk warning: "Similar setup in March led to 20% correction — set stops below $62K"

BAD Alpha Takes (DO NOT WRITE THESE):
• "Bitcoin price may go up due to positive news" ❌ (obvious, no insight)
• "This creates uncertainty in the market" ❌ (vague, no action)
• "Investors should watch developments closely" ❌ (useless advice)
• "The market reacted positively/negatively" ❌ (just restating the news)
• "This could impact crypto prices" ❌ (says nothing specific)

FORMULA FOR GOOD ALPHA TAKE:
[Specific observation] + [Historical/data context] + [Expected outcome with numbers/timing]

═══════════════════════════════════════════════════════════
CONTEXT TAG
═══════════════════════════════════════════════════════════

Format: [Strength] [Tone]

Strength: Low | Medium | High | Strong
Tone: Positive | Negative | Neutral | Critical

If Neutral, use ONLY "Neutral" (no strength modifier).

═══════════════════════════════════════════════════════════
HASHTAGS
═══════════════════════════════════════════════════════════

- Maximum 2 hashtags
- Max 10 characters each (no #MarketSentiment, #InstitutionalBuying)
- Good: #Bitcoin #ETH #BTC #Crypto #DeFi #Altcoins #Trading

═══════════════════════════════════════════════════════════
EXAMPLES
═══════════════════════════════════════════════════════════

Input: "Bitcoin ETF inflows hit $500M in one day"
ALPHA_TAKE: Inflows above $400M historically precede 8-12% rallies within 2 weeks. Watch $68K resistance — break confirms continuation to $72K.
CONTEXT_TAG: Strong positive
HASHTAGS: #Bitcoin #ETF

Input: "SEC delays Ethereum ETF decision"
ALPHA_TAKE: Third delay this year — pattern suggests approval unlikely before Q2. ETH typically drops 5-8% post-delay then recovers in 2 weeks.
CONTEXT_TAG: Medium negative
HASHTAGS: #Ethereum #SEC

Input: "Whale moves 10,000 BTC to Binance"
ALPHA_TAKE: Large exchange deposits often precede sells. Last 5 similar moves led to 3-7% dips within 48 hours. Consider taking partial profits.
CONTEXT_TAG: Medium negative
HASHTAGS: #Bitcoin #Whales

Input: "Fear & Greed Index drops to 25"
ALPHA_TAKE: Extreme fear readings below 25 preceded rallies 80% of the time in 2024. Historically best DCA entry zone — not time to panic sell.
CONTEXT_TAG: Medium positive
HASHTAGS: #Bitcoin #Crypto

Input: "Solana TVL reaches new ATH"
ALPHA_TAKE: TVL growth without price follow-through suggests accumulation phase. Previous ATH setups led to 30-50% moves within 30 days.
CONTEXT_TAG: High positive
HASHTAGS: #Solana #DeFi

REMEMBER:
- Give INSIGHTS, not summaries
- Include NUMBERS (%, days, price levels)
- Reference HISTORY or DATA
- Make it ACTIONABLE"""


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
                # НО НЕ убираем 📡 - его мы добавим сами при форматировании
                alpha_take = alpha_take.replace('ALPHA TAKE —', '').strip()
                alpha_take = alpha_take.replace('Structural / Macro', '').strip()
                alpha_take = alpha_take.replace('Flow & Positioning', '').strip()
                alpha_take = alpha_take.replace('Narrative & Attention', '').strip()
                
                # Убираем двойные пробелы
                while '  ' in alpha_take:
                    alpha_take = alpha_take.replace('  ', ' ')
                    
            elif line.startswith('CONTEXT_TAG:'):
                context_tag = line.replace('CONTEXT_TAG:', '').strip()
                
                if 'neutral' in context_tag.lower() and len(context_tag.split()) > 1:
                    context_tag = 'Neutral'
                
            elif line.startswith('HASHTAGS:'):
                hashtags = line.replace('HASHTAGS:', '').strip()
                
                tags_list = [tag.strip() for tag in hashtags.split() if tag.startswith('#')]
                if len(tags_list) > 3:
                    hashtags = ' '.join(tags_list[:3])
                    logger.info(f"  ⚠️ Trimmed hashtags from {len(tags_list)} to 3: {hashtags}")
        
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
    
    v2.7.0: Хэштеги вверху, максимум 2, не длинные
    
    Format:
    <hashtags>
    <title>
    
    <original_text_summary>
    
    [Alpha Take section]
    <alpha_take>
    
    Context: <context_tag>
    
    Args:
        title: Заголовок поста
        text: Оригинальный текст (TLDR)
        hashtags_fallback: Хештеги fallback (если AI не сгенерировал)
        ai_result: Результат от get_ai_alpha_take()
        
    Returns:
        str: Enhanced caption с Alpha Take
    """
    if not ai_result:
        # Без AI - старый формат (хэштеги вверху)
        clean_hashtags = sanitize_hashtags(hashtags_fallback, max_count=2, max_length=10)
        return f"{clean_hashtags}\n<b>{title}</b>\n\n{text}"
    
    alpha_take = ai_result.get('alpha_take', '')
    context_tag = ai_result.get('context_tag', '')
    hashtags_ai = ai_result.get('hashtags', '')
    
    # Используем AI хэштеги если есть, иначе fallback
    hashtags_raw = hashtags_ai if hashtags_ai else hashtags_fallback
    
    # Применяем политику хэштегов: max 2, короткие (<=10 символов без #)
    hashtags = sanitize_hashtags(hashtags_raw, max_count=2, max_length=10)
    
    # Убираем из текста блок "Alpha Take" если он там есть (для избежания дублирования)
    if 'Alpha Take' in text:
        alpha_start = text.find('Alpha Take')
        if alpha_start > 0:
            text = text[:alpha_start].strip()
    
    # Убираем вводные строки CMC (все варианты)
    import re
    text = re.sub(
        r"Here are the trending (?:narratives|cryptos) based on CoinMarketCap['\u2018\u2019\"]?s evolving (?:narrative|momentum) algorithm[^:]*:?\s*",
        '',
        text,
        flags=re.IGNORECASE
    )
    
    # Убираем "These are the upcoming crypto events..."
    text = re.sub(
        r"These are the upcoming crypto events that may impact crypto the most:?\s*",
        '',
        text,
        flags=re.IGNORECASE
    )
    
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
    
    # Формируем enhanced caption (хэштеги ВВЕРХУ)
    caption = f"{hashtags}\n" if hashtags else ""
    caption += f"<b>{title}</b>\n\n"
    
    # Оригинальный контент (очищенный от дублей)
    caption += f"{text}\n\n"
    
    # Alpha Take секция с 📡
    caption += f"📡 <b>Alpha Take</b>\n"
    caption += f"{alpha_take}\n\n"
    
    # Context Tag если есть
    if context_tag:
        caption += f"<i>Context: {context_tag}</i>"
    
    # Проверка на длину Telegram
    if len(caption) > 4000:
        logger.warning(f"⚠️ Caption слишком длинный ({len(caption)}), сокращаю оригинальный текст")
        # Агрессивное сокращение
        max_original_text = 400
        text = text[:max_original_text-3] + "..."
        
        caption = f"{hashtags}\n" if hashtags else ""
        caption += f"<b>{title}</b>\n\n"
        caption += f"{text}\n\n"
        caption += f"📡 <b>Alpha Take</b>\n"
        caption += f"{alpha_take}\n\n"
        if context_tag:
            caption += f"<i>Context: {context_tag}</i>"
    
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
        
        ai_limit = 240
        
        prompt = f"""Optimize this crypto tweet to fit in {ai_limit} characters.

Original tweet:
{initial_tweet}

Rules:
- Keep title: {title_safe}
- Condense the main message from Alpha Take into 1-2 sentences maximum
- Remove ALL hashtags if needed to fit the limit
- Target length: 220-240 characters (aim for this range for safety)
- CRITICAL: Each emoji counts as 2 characters - avoid emoji if possible
- Remove filler words: "however", "additionally", "furthermore", "meanwhile", etc
- Use short words and direct language
- Format: Keep double line break after title (\\n\\n), single line breaks elsewhere

Be concise but complete. Deliver clear actionable information.

Return ONLY the optimized tweet text, nothing else. No explanations."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You optimize tweets to character limits. Return only the tweet text."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.1
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
            logger.warning(f"  ⚠️ AI result too long: {get_twitter_length(optimized)} chars, truncating...")
            optimized = safe_truncate(optimized, max_length)
        
        final_length = get_twitter_length(optimized)
        if final_length > max_length:
            logger.error(f"  ✗ Still too long after truncate: {final_length} chars!")
            while get_twitter_length(optimized) > max_length and len(optimized) > 0:
                optimized = optimized[:-1]
            optimized = optimized.rstrip()
            if get_twitter_length(optimized + "...") <= max_length:
                optimized = optimized + "..."
        
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
