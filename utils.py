"""
utils.py - Общие утилиты для Radar_CMC_AI
Version: 1.0.0

Централизованные функции для:
- Подсчёта длины текста для Twitter
- Безопасного обрезания Unicode текста
- Работы с emoji
"""

import re
import logging

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# EMOJI DETECTION - ПОЛНЫЙ UNICODE PATTERN
# ══════════════════════════════════════════════════════════════════

# Полный паттерн для ОДНОГО emoji (без + чтобы считать каждый отдельно)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
    "\U0001F680-\U0001F6FF"  # Transport & Map
    "\U0001F700-\U0001F77F"  # Alchemical Symbols
    "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols & Pictographs
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols & Pictographs Extended-A
    "\U0001F1E0-\U0001F1FF"  # Flags (Regional Indicator)
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251"  # Enclosed characters
    "\U00002600-\U000026FF"  # Miscellaneous Symbols
    "\U00002700-\U000027BF"  # Dingbats
    "\U0000FE00-\U0000FE0F"  # Variation Selectors
    "\U0001F000-\U0001F02F"  # Mahjong Tiles
    "\U0001F0A0-\U0001F0FF"  # Playing Cards
    "]",  # NO + quantifier - match each emoji separately!
    flags=re.UNICODE
)


def get_twitter_length(text: str) -> int:
    """
    Вычисляет длину текста как её видит Twitter.
    
    Twitter считает:
    - Обычные символы = 1
    - Emoji = 2 (каждый emoji занимает 2 "weighted characters")
    - URL = 23 (но мы не обрабатываем URL тут)
    
    Args:
        text: Текст для подсчёта
        
    Returns:
        int: Длина текста для Twitter
    """
    if not text:
        return 0
    
    # Находим все emoji (каждый отдельно)
    emoji_matches = EMOJI_PATTERN.findall(text)
    emoji_count = len(emoji_matches)
    
    # Twitter: каждый emoji считается как 2, но занимает 1 позицию в строке
    # Поэтому: len(text) + emoji_count (добавляем +1 за каждый emoji)
    twitter_length = len(text) + emoji_count
    
    return twitter_length


def get_visual_length(text: str) -> int:
    """
    Вычисляет визуальную длину текста (для отладки).
    Каждый "видимый" символ = 1.
    """
    if not text:
        return 0
    
    # Убираем ZWJ и variation selectors для визуального подсчёта
    clean = re.sub(r'[\U0000200D\U0000FE0F]', '', text)
    return len(clean)


def safe_truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Безопасно обрезает текст учитывая emoji и Unicode.
    
    НЕ обрезает посередине:
    - Многобайтовых символов
    - Emoji sequences
    - Слов (если возможно)
    
    Args:
        text: Текст для обрезки
        max_length: Максимальная длина (Twitter length)
        suffix: Суффикс для обрезанного текста
        
    Returns:
        str: Обрезанный текст
    """
    if not text:
        return ""
    
    # Если уже помещается - возвращаем как есть
    if get_twitter_length(text) <= max_length:
        return text
    
    suffix_length = get_twitter_length(suffix)
    target_length = max_length - suffix_length
    
    if target_length <= 0:
        # Даже суффикс не помещается
        return text[:max_length] if max_length > 0 else ""
    
    # Разбиваем на "графемы" (визуальные символы)
    # Используем простой подход: идём по символам и проверяем длину
    result = []
    current_length = 0
    
    # Разбиваем текст на слова для умного обрезания
    words = text.split(' ')
    
    for i, word in enumerate(words):
        word_length = get_twitter_length(word)
        space_length = 1 if i > 0 else 0
        
        if current_length + space_length + word_length <= target_length:
            if i > 0:
                result.append(' ')
                current_length += 1
            result.append(word)
            current_length += word_length
        else:
            # Слово не помещается целиком
            if not result:
                # Первое слово - обрезаем его
                chars = list(word)
                for char in chars:
                    char_len = get_twitter_length(char)
                    if current_length + char_len <= target_length:
                        result.append(char)
                        current_length += char_len
                    else:
                        break
            break
    
    final_text = ''.join(result).rstrip()
    
    # Добавляем суффикс
    if final_text and get_twitter_length(final_text + suffix) <= max_length:
        return final_text + suffix
    
    return final_text


def count_emojis(text: str) -> int:
    """Считает количество emoji в тексте."""
    if not text:
        return 0
    return len(EMOJI_PATTERN.findall(text))


def remove_emojis(text: str) -> str:
    """Удаляет все emoji из текста."""
    if not text:
        return ""
    # Удаляем emoji и ZWJ
    text = EMOJI_PATTERN.sub('', text)
    text = re.sub(r'[\U0000200D\U0000FE0F]', '', text)
    return text


def truncate_to_tweet_length(text: str, max_length: int = 280) -> str:
    """
    Обрезает текст до длины твита.
    
    Умная обрезка:
    1. Пытается обрезать по предложению
    2. Затем по слову
    3. В крайнем случае по символу
    """
    if not text:
        return ""
    
    if get_twitter_length(text) <= max_length:
        return text
    
    # Пробуем обрезать по предложению
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = ""
    
    for sentence in sentences:
        test = result + (" " if result else "") + sentence
        if get_twitter_length(test) <= max_length - 3:  # -3 для "..."
            result = test
        else:
            break
    
    if result:
        if get_twitter_length(result) < max_length:
            return result
        return safe_truncate(result, max_length)
    
    # Fallback на safe_truncate
    return safe_truncate(text, max_length)


# ══════════════════════════════════════════════════════════════════
# ТЕСТЫ (для отладки)
# ══════════════════════════════════════════════════════════════════

def _test():
    """Тестирование функций."""
    # Twitter counting: regular char = 1, emoji = 2
    # Formula: len(text) + emoji_count (because len() counts emoji as 1, but Twitter counts as 2)
    test_cases = [
        ("Hello World", 11),           # 11 chars, 0 emoji = 11
        ("Hello 🌍", 8),                # 6 chars + 1 emoji = 6 + 2 = 8 (len=7, +1=8)
        ("🚀🚀🚀", 6),                   # 0 chars + 3 emoji = 0 + 6 = 6 (len=3, +3=6)
        ("Bitcoin 📈 to the moon 🚀", 25),  # 21 chars + 2 emoji = 21 + 4 = 25 (len=23, +2=25)
        ("Test", 4),                   # 4 chars, 0 emoji = 4
    ]
    
    print("Testing get_twitter_length():")
    all_passed = True
    for text, expected in test_cases:
        result = get_twitter_length(text)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} '{text}' → {result} (expected {expected})")
    
    print(f"\nAll tests passed: {'✓ YES' if all_passed else '✗ NO'}")
    
    print("\nTesting safe_truncate():")
    long_text = "This is a very long text with emoji 🚀 that needs to be truncated properly."
    truncated = safe_truncate(long_text, 50)
    print(f"  Original: {get_twitter_length(long_text)} chars")
    print(f"  Truncated: '{truncated}' ({get_twitter_length(truncated)} chars)")
    print(f"  Fits in 50: {'✓' if get_twitter_length(truncated) <= 50 else '✗'}")


if __name__ == "__main__":
    _test()
