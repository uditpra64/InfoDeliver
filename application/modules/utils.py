from difflib import SequenceMatcher
from typing import List, Optional


def similarity_ratio(word1: str, word2: str) -> float:
    """
    2つの文字列の類似度を返す。0～1の範囲。
    """
    return SequenceMatcher(None, word1, word2).ratio()


def return_most_similiar_word(
    input_word: str, word_list: List[str], threshold: float = 0.2
) -> Optional[str]:
    """
    `word_list` の各単語と `input_word` の類似度を比較し、最も高いものを返す。
    類似度が `threshold` 未満の場合は None を返す。
    """
    if not word_list:
        return None

    max_score = 0.0
    best_word = None
    for word in word_list:
        score = similarity_ratio(input_word, word)
        if score > max_score:
            max_score = score
            best_word = word
    return best_word if (best_word and max_score >= threshold) else None
