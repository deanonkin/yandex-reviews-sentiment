"""Оркестратор: парсинг → NLP → финальные CSV.

Запуск целиком:
    python pipeline.py

Можно пропустить уже выполненные шаги:
    python pipeline.py --skip-parse    # если reviews_raw.csv уже есть
    python pipeline.py --skip-nlp      # только парсинг
"""
import argparse
import sys
from pathlib import Path

from config import RAW_CSV


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-parse", action="store_true",
                    help="Не парсить (использовать существующий reviews_raw.csv)")
    ap.add_argument("--skip-nlp", action="store_true",
                    help="Не запускать NLP-обработку")
    args = ap.parse_args()

    if not args.skip_parse:
        print("=" * 60)
        print("ШАГ 1/2: Парсинг Яндекс.Карт")
        print("=" * 60)
        import parser as parser_mod
        parser_mod.main()
    else:
        if not Path(RAW_CSV).exists():
            sys.exit(f"Файл {RAW_CSV} не найден, пропустить парсинг нельзя")
        print(f"Парсинг пропущен, используем {RAW_CSV}")

    if not args.skip_nlp:
        print("\n" + "=" * 60)
        print("ШАГ 2/2: Перевод + ABSA + коррекция")
        print("=" * 60)
        import nlp as nlp_mod
        nlp_mod.main()
    else:
        print("NLP пропущен")


if __name__ == "__main__":
    main()