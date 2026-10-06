"""Перевод RU→EN, ABSA-анализ, regex-фильтр и гибридная коррекция.

Запуск:
    python nlp.py
Вход:  data/reviews_raw.csv
Выход: data/reviews_absa_final.csv, data/reviews_absa_long.csv
"""
import re
import time

import pandas as pd
import torch
from tqdm.auto import tqdm
from transformers import MarianMTModel, MarianTokenizer, pipeline

from config import (
    ASPECTS, ASPECT_KEYWORDS, MT_MODEL, ABSA_MODEL, TRANSLATE_BATCH,
    RAW_CSV, TRANSLATED_CSV, FINAL_WIDE_CSV, FINAL_LONG_CSV,
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ---------- Модели ----------

def load_models():
    """Загружает переводчик и ABSA-модель один раз."""
    print(f"Device: {DEVICE}")
    print(f"Загружаем переводчик {MT_MODEL}...")
    tok = MarianTokenizer.from_pretrained(MT_MODEL)
    mt = MarianMTModel.from_pretrained(MT_MODEL).to(DEVICE)

    print(f"Загружаем ABSA-модель {ABSA_MODEL}...")
    absa = pipeline(
        "text-classification",
        model=ABSA_MODEL,
        device=0 if DEVICE == "cuda" else -1,
    )
    print("Модели загружены")
    return tok, mt, absa


# ---------- Перевод ----------

def translate_batch(texts: list[str], tok, mt, batch_size: int = TRANSLATE_BATCH) -> list[str]:
    """Переводит список русских текстов на английский батчами."""
    out_all = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            inputs = tok(
                batch, return_tensors="pt", padding=True,
                truncation=True, max_length=512,
            ).to(DEVICE)
            with torch.no_grad():
                gen = mt.generate(**inputs, max_length=512)
            out_all.extend(tok.batch_decode(gen, skip_special_tokens=True))
        except Exception as e:
            print(f"  Ошибка на батче {i}: {e}")
            out_all.extend([""] * len(batch))
    return out_all


# ---------- ABSA ----------

def absa_analyze(df: pd.DataFrame, absa) -> pd.DataFrame:
    """Заполняет колонки asp_<aspect>_sent и asp_<aspect>_score."""
    for _, asp_en in ASPECTS:
        col = asp_en.replace(" ", "_")
        df[f"asp_{col}_sent"] = None
        df[f"asp_{col}_score"] = None

    for i in tqdm(range(len(df)), desc="ABSA"):
        text_en = df.at[i, "text_en"]
        if not text_en or len(text_en) < 3:
            for _, asp_en in ASPECTS:
                col = asp_en.replace(" ", "_")
                df.at[i, f"asp_{col}_sent"] = "unknown"
                df.at[i, f"asp_{col}_score"] = 0.0
            continue
        for _, asp_en in ASPECTS:
            col = asp_en.replace(" ", "_")
            try:
                r = absa(text_en, text_pair=asp_en, truncation=True, max_length=512)
                df.at[i, f"asp_{col}_sent"] = r[0]["label"].lower()
                df.at[i, f"asp_{col}_score"] = round(r[0]["score"], 3)
            except Exception:
                df.at[i, f"asp_{col}_sent"] = "error"
                df.at[i, f"asp_{col}_score"] = 0.0
    return df


# ---------- Regex-фильтр «упомянут ли аспект» ----------

def _aspect_mentioned(text_ru: str, aspect_en: str) -> bool:
    pattern = ASPECT_KEYWORDS.get(aspect_en, "")
    if not pattern:
        return True
    return bool(re.search(pattern, (text_ru or "").lower()))


def apply_keyword_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Помечает 'not_mentioned' аспекты, которых нет в тексте отзыва."""
    for _, asp_en in ASPECTS:
        col = asp_en.replace(" ", "_")
        sent_col = f"asp_{col}_sent"
        score_col = f"asp_{col}_score"
        new_sents, new_scores = [], []
        for _, row in df.iterrows():
            if _aspect_mentioned(row["text"], asp_en):
                new_sents.append(row[sent_col])
                new_scores.append(row[score_col])
            else:
                new_sents.append("not_mentioned")
                new_scores.append(0.0)
        df[sent_col] = new_sents
        df[score_col] = new_scores
    return df


# ---------- Гибридная коррекция по рейтингу ----------

def adjust_sentiment_v2(rating, sent: str, score: float) -> str:
    """Корректирует тональность аспекта по рейтингу отзыва."""
    if rating is None or sent in ("not_mentioned", "unknown", "error"):
        return sent

    if rating == 5:
        if sent == "negative" and score < 0.95:
            return "positive"
        if sent == "neutral":
            return "positive"

    if rating == 4:
        if sent == "negative" and score < 0.85:
            return "positive"
        if sent == "neutral":
            return "positive"

    if rating <= 2:
        if sent == "positive" and score < 0.90:
            return "negative"
        if sent == "neutral":
            return "negative"

    if rating == 3 and score < 0.70:
        return "neutral"

    return sent


def apply_rating_correction(df: pd.DataFrame) -> pd.DataFrame:
    for _, asp_en in ASPECTS:
        col = asp_en.replace(" ", "_")
        sent_col = f"asp_{col}_sent"
        df[sent_col] = [
            adjust_sentiment_v2(row["rating"], row[sent_col], row[f"asp_{col}_score"])
            for _, row in df.iterrows()
        ]
    return df


# ---------- Длинный формат (для DataLens) ----------

def to_long_format(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        for asp_ru, asp_en in ASPECTS:
            col = asp_en.replace(" ", "_")
            rows.append({
                "establishment_id": row["establishment_id"],
                "establishment_name": row["establishment_name"],
                "author": row["author"],
                "rating": row["rating"],
                "date": row["date"],
                "aspect_ru": asp_ru,
                "aspect_en": asp_en,
                "sentiment": row[f"asp_{col}_sent"],
                "score": row[f"asp_{col}_score"],
            })
    return pd.DataFrame(rows)


# ---------- Главный поток ----------

def main() -> None:
    df = pd.read_csv(RAW_CSV)
    df = df[df["text"].fillna("").str.len() > 3].reset_index(drop=True)
    print(f"Загружено отзывов: {len(df)}")

    tok, mt, absa = load_models()

    # 1. Перевод
    print("\n[1/4] Перевод RU→EN...")
    t0 = time.time()
    df["text_en"] = translate_batch(df["text"].tolist(), tok, mt)
    print(f"  Готово за {(time.time() - t0) / 60:.1f} мин, "
          f"успешно: {(df['text_en'].str.len() > 0).sum()}/{len(df)}")
    df.to_csv(TRANSLATED_CSV, index=False, encoding="utf-8-sig")

    # 2. ABSA
    print("\n[2/4] ABSA-анализ...")
    t0 = time.time()
    df = absa_analyze(df, absa)
    print(f"  Готово за {(time.time() - t0) / 60:.1f} мин")

    # 3. Regex-фильтр
    print("\n[3/4] Фильтр «упомянут ли аспект»...")
    df = apply_keyword_filter(df)

    # 4. Коррекция по рейтингу
    print("\n[4/4] Гибридная коррекция по рейтингу...")
    df = apply_rating_correction(df)

    # Сохраняем
    df.to_csv(FINAL_WIDE_CSV, index=False, encoding="utf-8-sig")
    long_df = to_long_format(df)
    long_df.to_csv(FINAL_LONG_CSV, index=False, encoding="utf-8-sig")

    # Итоговая сводка
    print(f"\n{'=' * 60}")
    print("ИТОГИ")
    print(f"{'=' * 60}")
    print(f"Отзывов: {len(df)} | Заведений: {df['establishment_id'].nunique()}")
    print("\nТональность по аспектам (без not_mentioned):")
    for asp_ru, asp_en in ASPECTS:
        col = asp_en.replace(" ", "_")
        sub = df[df[f"asp_{col}_sent"] != "not_mentioned"][f"asp_{col}_sent"].value_counts()
        total = sub.sum()
        neg_pct = round(sub.get("negative", 0) / total * 100, 1) if total else 0.0
        print(f"  {asp_ru:25s} упомянут в {total:3d} | негатив: {neg_pct}%")
    print(f"\nСохранено: {FINAL_WIDE_CSV}")
    print(f"Сохранено: {FINAL_LONG_CSV} ({len(long_df)} строк)")


if __name__ == "__main__":
    main()