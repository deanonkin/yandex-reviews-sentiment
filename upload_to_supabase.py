"""Инкрементальная загрузка отзывов в Supabase.

Запуск:
    SUPABASE_DB_URL="postgresql://..." python upload_to_supabase.py

Логика:
    1. Читаем из БД ключи уже загруженных отзывов.
    2. Из свежего CSV берём только те строки, которых нет в БД.
    3. Вставляем новые reviews, получаем их review_id.
    4. Для новых reviews вставляем аспекты в review_aspects.

Старые записи в БД не трогаются — накопление работает.
"""
import os
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config import ASPECTS, FINAL_WIDE_CSV


# ---------- Вспомогательные функции ----------

def _normalize_date(value) -> str:
    """Приводит дату к единому виду 'YYYY-MM-DD HH:MM:SS'.

    Это нужно, чтобы сравнение ключей из CSV и из БД было корректным
    независимо от того, в каком формате пришла дата.
    """
    if pd.isna(value):
        return ""
    dt = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(dt):
        return str(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _make_key(est_id, author, text, date_val) -> tuple:
    """Составной ключ отзыва для дедупликации."""
    return (
        (est_id or "").strip(),
        (author or "").strip(),
        (text or "").strip(),
        _normalize_date(date_val),
    )


# ---------- Чтение существующих ключей из БД ----------

def fetch_existing_keys(cur) -> set:
    """Возвращает set ключей всех отзывов, уже лежащих в БД."""
    cur.execute("""
        SELECT establishment_id, author, text_ru, review_date
        FROM reviews
    """)
    keys = set()
    for est_id, author, text, date_val in cur.fetchall():
        keys.add(_make_key(est_id, author, text, date_val))
    return keys


# ---------- Основная загрузка ----------

def load_to_supabase(db_url: str, wide_csv) -> None:
    df = pd.read_csv(wide_csv)
    print(f"Прочитано из CSV: {len(df)} отзывов")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # 1. Что уже есть в БД
    existing = fetch_existing_keys(cur)
    print(f"Уже в БД (уникальных ключей): {len(existing)}")

    # 2. Отбираем только новые строки
    df["_key"] = [
        _make_key(row["establishment_id"], row["author"], row["text"], row["date"])
        for _, row in df.iterrows()
    ]
    df_new = df[~df["_key"].isin(existing)].drop(columns=["_key"]).reset_index(drop=True)

    print(f"Новых отзывов к загрузке: {len(df_new)}")

    if len(df_new) == 0:
        print("Нечего загружать — все отзывы уже в БД.")
        cur.close()
        conn.close()
        return

    # 3. Вставляем новые reviews
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
        for _, row in df_new.iterrows()
    ]

    # page_size = len(...), чтобы RETURNING вернул review_id в том же порядке
    inserted = execute_values(
        cur,
        """
        INSERT INTO reviews
            (establishment_id, establishment_name, author,
             rating, review_date, text_ru, text_en)
        VALUES %s
        RETURNING review_id
        """,
        reviews_rows,
        page_size=max(len(reviews_rows), 1),
        fetch=True,
    )
    review_ids = [r[0] for r in inserted]
    df_new = df_new.assign(review_id=review_ids)
    print(f"Вставлено reviews: {len(review_ids)}")

    # 4. Вставляем аспекты для новых reviews
    aspect_rows = []
    for _, row in df_new.iterrows():
        rid = row["review_id"]
        for asp_ru, asp_en in ASPECTS:
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
        aspect_rows,
        page_size=500,
    )
    print(f"Вставлено review_aspects: {len(aspect_rows)}")

    conn.commit()

    # 5. Итоговая сводка
    cur.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM review_aspects")
    total_aspects = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(f"\n{'=' * 60}")
    print("ИТОГИ ЗАГРУЗКИ")
    print(f"{'=' * 60}")
    print(f"Добавлено новых отзывов:  {len(review_ids)}")
    print(f"Добавлено новых аспектов: {len(aspect_rows)}")
    print(f"Всего отзывов в БД:       {total_reviews}")
    print(f"Всего аспектов в БД:      {total_aspects}")


def main() -> None:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        sys.exit("Не задана переменная SUPABASE_DB_URL")
    load_to_supabase(db_url, FINAL_WIDE_CSV)


if __name__ == "__main__":
    main()