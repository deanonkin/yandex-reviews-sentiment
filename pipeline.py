"""Оркестратор: парсинг → NLP → загрузка в Supabase."""
import argparse
import os
import sys
from pathlib import Path

from config import RAW_CSV, FINAL_WIDE_CSV


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-parse",  action="store_true")
    ap.add_argument("--skip-nlp",    action="store_true")
    ap.add_argument("--skip-upload", action="store_true")
    args = ap.parse_args()

    if not args.skip_parse:
        print("=" * 60); print("ШАГ 1/3: Парсинг Яндекс.Карт"); print("=" * 60)
        import parser as parser_mod
        parser_mod.main()
    elif not Path(RAW_CSV).exists():
        sys.exit(f"Файл {RAW_CSV} не найден")
    else:
        print(f"Парсинг пропущен, используем {RAW_CSV}")

    if not args.skip_nlp:
        print("\n" + "=" * 60); print("ШАГ 2/3: Перевод + ABSA + коррекция"); print("=" * 60)
        import nlp as nlp_mod
        nlp_mod.main()
    elif not Path(FINAL_WIDE_CSV).exists():
        sys.exit(f"Файл {FINAL_WIDE_CSV} не найден")
    else:
        print(f"NLP пропущен, используем {FINAL_WIDE_CSV}")

    if not args.skip_upload:
        print("\n" + "=" * 60); print("ШАГ 3/3: Загрузка в Supabase"); print("=" * 60)
        if not os.getenv("SUPABASE_DB_URL"):
            sys.exit("Не задана переменная SUPABASE_DB_URL")
        import upload_to_supabase as upload_mod
        upload_mod.main()
    else:
        print("Загрузка пропущена")


if __name__ == "__main__":
    main()