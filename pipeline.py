"""Оркестратор: парсинг → NLP → загрузка в Supabase.

Оптимизация: если после парсинга новых отзывов не обнаружено,
шаги NLP и upload пропускаются (экономия ~20 минут).
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2

from config import RAW_CSV, FINAL_WIDE_CSV


def count_new_reviews(csv_path, db_url: str) -> int:
    """Считает, сколько отзывов из CSV ещё не загружено в БД.

    Возвращает -1, если не удалось подключиться к БД
    (в этом случае NLP запускается всегда — безопасный fallback).
    """
    if not Path(csv_path).exists():
        return -1

    try:
        from upload_to_supabase import _make_key, fetch_existing_keys

        df = pd.read_csv(csv_path)
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        existing = fetch_existing_keys(cur)
        cur.close()
        conn.close()

        df["_key"] = [
            _make_key(r["establishment_id"], r["author"], r["text"], r["date"])
            for _, r in df.iterrows()
        ]
        new_count = int((~df["_key"].isin(existing)).sum())
        return new_count

    except Exception as e:
        print(f"  Не удалось проверить новые отзывы ({e}), пропускаем оптимизацию.")
        return -1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-parse",  action="store_true")
    ap.add_argument("--skip-nlp",    action="store_true")
    ap.add_argument("--skip-upload", action="store_true")
    args = ap.parse_args()

    # --- ШАГ 1: Парсинг ---
    if not args.skip_parse:
        print("=" * 60); print("ШАГ 1/3: Парсинг Яндекс.Карт"); print("=" * 60)
        import parser as parser_mod
        parser_mod.main()
    elif not Path(RAW_CSV).exists():
        sys.exit(f"Файл {RAW_CSV} не найден")
    else:
        print(f"Парсинг пропущен, используем {RAW_CSV}")

    # --- Оптимизация: проверка новых отзывов ---
    db_url = os.getenv("SUPABASE_DB_URL")
    if db_url and not args.skip_upload:
        print("\n" + "-" * 60)
        print("Проверка новых отзывов...")
        new_count = count_new_reviews(RAW_CSV, db_url)
        print(f"  Новых отзывов к обработке: {new_count}")

        if new_count == 0:
            print("\n" + "=" * 60)
            print("Новых отзывов нет — NLP и upload пропущены.")
            print("Экономия ~20 минут. До следующего запуска.")
            print("=" * 60)
            return

    # --- ШАГ 2: NLP ---
    if not args.skip_nlp:
        print("\n" + "=" * 60); print("ШАГ 2/3: Перевод + ABSA + коррекция"); print("=" * 60)
        import nlp as nlp_mod
        nlp_mod.main()
    elif not Path(FINAL_WIDE_CSV).exists():
        sys.exit(f"Файл {FINAL_WIDE_CSV} не найден")
    else:
        print(f"NLP пропущен, используем {FINAL_WIDE_CSV}")

    # --- ШАГ 3: Загрузка ---
    if not args.skip_upload:
        print("\n" + "=" * 60); print("ШАГ 3/3: Загрузка в Supabase"); print("=" * 60)
        if not db_url:
            sys.exit("Не задана переменная SUPABASE_DB_URL")
        import upload_to_supabase as upload_mod
        upload_mod.main()
    else:
        print("Загрузка пропущена")


if __name__ == "__main__":
    main()