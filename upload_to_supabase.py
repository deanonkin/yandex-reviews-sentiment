"""Загрузка обработанных отзывов в Supabase.

Запуск:
    SUPABASE_DB_URL="postgresql://..." python upload_to_supabase.py

Для MVP: полностью перезаписывает данные (TRUNCATE + INSERT).
"""
import os
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config import FINAL_WIDE_CSV, FINAL_LONG_CSV


def load_to_supabase(db_url: str, wide_csv, long_csv) -> None:
    df = pd.read_csv(wide_csv)
    long_df = pd.read_csv(long_csv)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Для MVP очищаем и грузим заново. Инкремент добавим позже.
    cur.execute("TRUNCATE review_aspects, reviews RESTART IDENTITY CASCADE;")

    # --- 1. reviews ---
    reviews_rows = [
        (
            row["establishment_id"],
            row["establishment_name"],
            row["author"],
            int(row["rating"]) if pd.notna(row["rating"]) else None,
            row["date"],
            row["text"],
            row["text_en"],
        )
        for _, row in df.iterrows()
    ]

    inserted = execute_values(
        cur,
        """
        INSERT INTO reviews
            (establishment_id, establishment_name, author,
             rating, review_date, text_ru, text_en)
        VALUES %s
        RETURNING review_id
        """,
        reviews_rows, page_size=100, fetch=True,
    )
    review_ids = [r[0] for r in inserted]

    # Позиционная привязка: review_ids[0] соответствует df.iloc[0]
    df = df.assign(review_id=review_ids)

    # --- 2. review_aspects ---
    # Пересобираем long из wide с проставленным review_id
    aspect_rows = []
    for _, row in df.iterrows():
        rid = row["review_id"]
        for asp_ru, asp_en in [
            ("еда", "food"), ("обслуживание", "service"),
            ("чистота", "cleanliness"), ("цена", "price"),
            ("скорость обслуживания", "speed of service"),
        ]:
            col = asp_en.replace(" ", "_")
            aspect_rows.append((
                rid,
                asp_ru,
                asp_en,
                row[f"asp_{col}_sent"],
                float(row[f"asp_{col}_score"]) if pd.notna(row[f"asp_{col}_score"]) else 0.0,
            ))

    execute_values(
        cur,
        """
        INSERT INTO review_aspects
            (review_id, aspect_ru, aspect_en, sentiment, score)
        VALUES %s
        """,
        aspect_rows, page_size=500,
    )

    conn.commit()
    cur.close()
    conn.close()

    print(f"✓ reviews:        {len(reviews_rows)}")
    print(f"✓ review_aspects: {len(aspect_rows)}")


def main() -> None:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        sys.exit("Не задана переменная SUPABASE_DB_URL")
    load_to_supabase(db_url, FINAL_WIDE_CSV, FINAL_LONG_CSV)


if __name__ == "__main__":
    main()