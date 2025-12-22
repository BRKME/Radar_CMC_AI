"""
OpenAI Integration для CMC AI - Alpha Take для текстовых новостей
Version: 2.3.0 - Updated to 1-sentence Alpha Take format
Генерирует Alpha Take, Context Tag и Hashtags для новостей CoinMarketCap AI

ОБНОВЛЕНО В v2.3.0:
- НОВЫЙ MASTER PROMPT: 1 sentence preferred (было: 2-4 sentences)
- Optimized for high-density delivery (feed/alerts/SMS)
- Более концентрированный и сжатый Alpha Take

ОБНОВЛЕНО В v2.2.0:
- Обновлен MASTER PROMPT на финальную версию
- Строже HARD RULES: No restating headline, No mechanical summary
- Alpha Take теперь синтезирует: input + macro/liquidity/regulatory/narrative backdrop
- Требование контекстуальности: never fragmented or isolated from wider news flow
- Запрет на generic phrases
- AI генерирует хэштеги

ОБНОВЛЕНО В v2.1.0:
- ОТКАТ: AI снова генерирует хэштеги (как было в v1.0)
- Новый institutional-grade промпт
- Запрещены эмодзи в Alpha Take и Context Tag
"""

import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Инициализация клиента
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("✓ OpenAI client initialized for CMC AI v2.3")
    except Exception as e:
        logger.error(f"✗ Failed to initialize OpenAI client: {e}")
        client = None
else:
    logger.warning("⚠️ OPENAI_API_KEY not found - Alpha Take generation disabled")


# MASTER PROMPT для CMC AI новостей - INSTITUTIONAL GRADE v2.3
CMC_NEWS_MASTER_PROMPT = """🧠 MASTER PROMPT — Crypto Radar / OracAI

"Alpha Take — Institutional Market Intelligence"

ROLE

You are an institutional-grade crypto research assistant.

Your task is to transform raw crypto news, data, screenshots, indicators, or narratives into high-signal market intelligence suitable for professional investors.

You do not give trading advice.
You do not issue explicit price predictions unless strictly data-driven and probabilistic.
You focus on market regimes, positioning, flows, incentives, liquidity, and narratives — not outcomes.

Tone: concise, analytical, emotionally neutral
Audience: US-based, market-literate crypto investors
Writing style: buy-side / sell-side research note
Constraint: optimized for high-density delivery (feed / alerts / SMS)

HARD RULES (STRICT)

❌ No emojis
❌ No calls to action
❌ No execution or strategy language
❌ No hype, storytelling, or motivational tone
❌ No restating the headline or data inside Alpha Take
❌ No mechanical summary of the input
❌ No simplistic "this is good/bad" framing

Bullish / bearish wording is not allowed in body text.
If sentiment must be conveyed, it must be expressed structurally (positioning, flows, participation), never directionally.

OUTPUT FORMAT (MANDATORY)

ALPHA_TAKE: [1 sentence preferred. Maximum 2 sentences only if additional structure is essential. Dense, precise, non-repetitive. Zero retelling of input. Must synthesize: (1) specific input AND (2) prevailing macro, liquidity, regulatory, and narrative backdrop. Never fragmented or isolated from wider news flow.]

CONTEXT_TAG: [ONE line only. ONE category only. 2–4 words. No emojis. No directional bias.]

HASHTAGS: [Generate 3-5 relevant, contextual hashtags based on current market state and content. Use professional vocabulary. Format: #Tag1 #Tag2 #Tag3]

◼ ALPHA TAKE — CORE DEFINITION

The Alpha Take answers one question only:

"What does this mean for market participants right now, given the broader market and news environment?"

It is:
• Interpretive, not predictive
• Descriptive, not prescriptive
• About behavior and structure, not outcomes
• Contextual — never fragmented or isolated from the wider news flow

Alpha Take must synthesize:
• the specific input (news / data / indicator), and
• the prevailing macro, liquidity, regulatory, and narrative backdrop

◼ ALPHA TAKE — STYLE RULES

Length

1 sentence preferred for:
• sentiment dashboards
• recurring indicators
• positioning snapshots

Up to 2–3 sentences max only if additional structure is added

Writing constraints
• Dense, precise, non-repetitive
• Zero retelling of the input
• Zero generic filler ("creates uncertainty", "could impact markets")

Alpha Take must emphasize second-order effects, such as:
• shifts in incentives
• changes in participant behavior
• liquidity sensitivity or constraints
• crowding vs dispersion
• narrative fatigue, overlap, or fragmentation
• regime stability vs fragility

If relevant, state what would need to change for the interpretation to shift — without implying a trade.

THREE TYPES OF ◼ ALPHA TAKE

Select exactly ONE per analysis:

1️⃣ Alpha Take — Flow & Positioning

Use when content includes:
• ETF inflows / outflows
• Open interest, liquidations
• Funding rates, leverage
• Bitcoin dominance
• On-chain positioning

Primary focus:
• Risk appetite shifts
• De-risking vs re-leveraging
• Capital concentration or dispersion
• Asymmetry building or unwinding

2️⃣ Alpha Take — Narrative & Attention

Use when content includes:
• Sector or theme narratives (L1, AI, DeFi, infra)
• Social or media momentum
• KOL-driven or narrative repricing

Primary focus:
• Where attention is rotating vs where capital is not
• Narrative crowding vs early-stage themes
• Consensus formation, fatigue, or fragmentation

3️⃣ Alpha Take — Structural / Macro

Use when content includes:
• Regulation or policy
• Macro developments
• Market structure changes
• Adoption or infrastructure shifts

Primary focus:
• Regime transitions
• Long-duration constraints or tail risks
• Frictions affecting liquidity, access, or participation

CONTEXT TAG — FINAL LINE (MANDATORY)

Rules:
• ONE line only
• ONE category only
• 2–4 words
• No emojis
• No directional bias
• Context ≠ signal

OPTIMIZED CONTEXT TAG CATEGORIES

🧩 Risk Regime (macro liquidity & risk appetite)
Examples:
• Risk-off environment
• Fragile risk-on
• Liquidity-driven regime
• High uncertainty phase

📈 Market Regime (price behavior & structure)
Examples:
• Volatile range
• Compression phase
• Trend transition phase
• Momentum exhaustion

⏳ Time Horizon (dominant timeframe implied)
Examples:
• Near-term volatility
• Short-term cautious
• Medium-term constructive
• Long-duration shift

Use symbol ◼ before Alpha Take Title

🧠 Positioning Bias (crowding & exposure)
Examples:
• Defensive positioning
• Light exposure
• Crowded longs
• De-risked market

DECISION TREE — CONTEXT TAG

• References flows, leverage, liquidity → Risk Regime / Positioning Bias
• Describes volatility or price structure → Market Regime
• Emphasizes duration over price → Time Horizon
• Core insight is crowding or exposure → Positioning Bias

⚠️ Never mix categories
⚠️ Avoid mechanical repetition across posts

WHEN ◼ ALPHA TAKE IS OPTIONAL

Alpha Take may be omitted only for:
• Ultra-short headlines
• Pure data prints
• Repeated intraday updates

➡️ Context Tag may still be used alone.

HASHTAGS GUIDELINES

• Generate 3-5 hashtags relevant to the content
• Use professional, market-focused vocabulary
• Avoid generic tags like #Crypto #Bitcoin unless specifically relevant
• Examples: #BTCFlows #InstitutionalDemand #MacroRisk #DeFiRotation #AltcoinSeason
• Format: #CamelCase for multi-word tags

QUALITY CHECK (INTERNAL)

Before finalizing, verify:
• Does this reduce noise?
• Does it explain structure, not summary?
• Is it anchored in the broader news and regime context, not isolated?
• Would a hedge fund analyst find it immediately useful?

If yes → publish
If no → refine

EXAMPLE OUTPUT

Input: "Bitcoin ETF flows show sustained positive inflows after weeks of outflows. Meanwhile, altcoins remain suppressed with dominance near 60%."

ALPHA_TAKE: Renewed institutional flows suggest selective re-entry rather than broad risk appetite, amplified by continued macro uncertainty around Fed policy and persistent regulatory overhang that constrains meaningful rotation into alts.

CONTEXT_TAG: Selective risk-on

HASHTAGS: #BTCFlows #InstitutionalDemand #SelectiveRisk

Remember:
• NO emojis in Alpha Take or Context Tag
• NO restating the headline
• NO mechanical summary
• ALWAYS contextualize within broader market environment
• Hashtags should be generated and relevant
• Professional institutional tone
• 1 SENTENCE PREFERRED (2-3 max if structure needed)
"""


def get_ai_alpha_take(news_text, question_context=""):
    """
    Получает Alpha Take от OpenAI для текстовой новости
    
    v2.3: 1 sentence preferred Alpha Take (was: 2-4 sentences)
    
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
        
        logger.info(f"🤖 Requesting Alpha Take from OpenAI (v2.3 - 1 sentence)...")
        logger.info(f"   Input length: {len(full_input)} chars")
        
        # Вызываем OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Быстрая и недорогая модель
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
            max_tokens=250,  # Уменьшено с 350 (короче Alpha Take)
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
            if line.startswith('ALPHA_TAKE:'):
                alpha_take = line.replace('ALPHA_TAKE:', '').strip()
            elif line.startswith('CONTEXT_TAG:'):
                context_tag = line.replace('CONTEXT_TAG:', '').strip()
            elif line.startswith('HASHTAGS:'):
                hashtags = line.replace('HASHTAGS:', '').strip()
        
        # Валидация
        if not alpha_take:
            logger.warning(f"Could not parse Alpha Take from response")
            logger.warning(f"  Response: {content[:200]}...")
            # Fallback: используем весь ответ
            alpha_take = content
        
        logger.info(f"  ✓ Alpha Take: {alpha_take[:100]}...")
        if context_tag:
            logger.info(f"  ✓ Context Tag: {context_tag}")
        if hashtags:
            logger.info(f"  ✓ AI Hashtags: {hashtags}")
        
        return {
            "alpha_take": alpha_take,
            "context_tag": context_tag,
            "hashtags": hashtags  # v2.3: AI генерирует хэштеги
        }
        
    except Exception as e:
        logger.error(f"Error getting Alpha Take: {e}")
        import traceback
        traceback.print_exc()
        return None


def enhance_caption_with_alpha_take(title, text, hashtags_fallback, ai_result):
    """
    Добавляет Alpha Take к caption для Telegram
    
    v2.3: Supports shorter 1-sentence Alpha Take
    
    Format:
    <title>
    
    <original_text_summary>
    
    Alpha Take
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
    
    # v2.3: Используем AI хэштеги если есть, иначе fallback
    hashtags = hashtags_ai if hashtags_ai else hashtags_fallback
    
    # Сокращаем оригинальный текст если добавляем Alpha Take
    # Чтобы уместиться в Telegram лимиты
    max_original_text = 800  # Оставляем место для Alpha Take
    if len(text) > max_original_text:
        text = text[:max_original_text-3] + "..."
    
    # Формируем enhanced caption
    caption = f"<b>{title}</b>\n\n"
    
    # Оригинальный контент (сокращенный)
    caption += f"{text}\n\n"
    
    # Alpha Take секция
    caption += f"<b>Alpha Take</b>\n"
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
        caption += f"<b>Alpha Take</b>\n"
        caption += f"{alpha_take}\n\n"
        if context_tag:
            caption += f"<i>Context: {context_tag}</i>\n\n"
        caption += f"{hashtags}"
    
    return caption


def enhance_twitter_with_alpha_take(title, alpha_take, context_tag, hashtags):
    """
    Создаёт Twitter контент с Alpha Take
    
    v2.3: Works with shorter 1-sentence Alpha Take
    
    Args:
        title: Заголовок
        alpha_take: Alpha Take текст (1 sentence preferred)
        context_tag: Context Tag
        hashtags: Хештеги (AI-generated или fallback)
        
    Returns:
        str: Twitter-formatted текст (single tweet)
    """
    # Twitter лимит
    max_length = 270
    
    # Формат: Title + Alpha Take + Context + Hashtags
    
    # Резервируем место
    reserved = len(title) + len(hashtags) + 20  # +20 для форматирования
    if context_tag:
        reserved += len(f"Context: {context_tag}") + 4
    
    available_for_alpha = max_length - reserved
    
    # v2.3: Alpha Take теперь короче (1 sentence), обычно влезет
    if len(alpha_take) > available_for_alpha:
        # Сокращаем только если действительно не влезает
        short_alpha = alpha_take[:available_for_alpha-3] + "..."
    else:
        short_alpha = alpha_take
    
    # Собираем твит
    tweet = f"{title}\n\n{short_alpha}"
    
    if context_tag:
        tweet += f"\n\nContext: {context_tag}"
    
    tweet += f"\n\n{hashtags}"
    
    # Финальная проверка
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."
    
    return tweet
