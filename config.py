"""Конфигурация проекта: URL заведений, аспекты, regex, пути."""
import os
from pathlib import Path

# --- Пути ---
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

RAW_CSV = DATA_DIR / "reviews_raw.csv"
TRANSLATED_CSV = DATA_DIR / "reviews_translated.csv"
FINAL_WIDE_CSV = DATA_DIR / "reviews_absa_final.csv"
FINAL_LONG_CSV = DATA_DIR / "reviews_absa_long.csv"

# --- Заведения сети «Вкусно — и точка» ---
ESTABLISHMENTS = [
    {"id": "leningradsky_36",    "name": "Ленинградский 36",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/20894249870/reviews/"},
    {"id": "okhotny_ryad",       "name": "Охотный ряд",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/128463520794/reviews/"},
    {"id": "nikolskaya",         "name": "Никольская",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/199585451160/reviews/"},
    {"id": "pushkinskaya",       "name": "Пушкинская",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/52488537362/reviews/"},
    {"id": "ryazansky_prospekt", "name": "Рязанский проспект",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/52049393799/reviews/"},
    {"id": "novy_arbat",         "name": "Новый Арбат",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/128565553022/reviews/"},
    {"id": "tsdm",               "name": "ЦДМ",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/127200748000/reviews/"},
    {"id": "tretyakovskaya",     "name": "Третьяковская",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/28055216439/reviews/"},
    {"id": "ulitsa_1905_goda",   "name": "Улица 1905 года",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/57373394069/reviews/"},
    {"id": "afimall",            "name": "Афимолл",
     "url": "https://yandex.ru/maps/org/vkusno_i_tochka/141972070745/reviews/"},
]

# --- Параметры парсинга ---
MAX_REVIEWS_PER_EST = 50
PARSER_SLEEP_SEC = 8
PARSER_HEADLESS = True
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# --- Аспекты: (отображаемое имя, английское имя для модели) ---
ASPECTS = [
    ("еда",                   "food"),
    ("обслуживание",          "service"),
    ("чистота",               "cleanliness"),
    ("цена",                  "price"),
    ("скорость обслуживания", "speed of service"),
]

# --- Regex-ключевые слова для фильтра «упомянут ли аспект» ---
ASPECT_KEYWORDS = {
    "food": r"\bед[аыу]|\bвкус|\bбургер|\bкартош|\bнаггетс|\bкофе|\bморожен|\bролл|\bсоус|\bблюд|\bпорци|\bфри\b|\bнапит|\bдесерт|\bсыр\b|\bмяс",
    "service": r"\bперсонал|\bофициант|\bсотрудник|\bкассир|\bхам|\bвежлив|\bобслуж|\bработник|\bадминистратор|\bдевушк|\bмальчик",
    "cleanliness": r"\bгряз|\bчист|\bубир|\bмусор|\bпыль|\bвоня|\bзапах|\bтуалет|\bподнос|\bдиван|\bпомещен|\bуборн|\bстол[аыуе]?\b|\bпол[аыуе]?\b",
    "price": r"\bцен|\bдорог|\bдешев|\bрубл|\bстоим|\bчек\b|\bденьг|\bбюджет|\bпереплат|\bскидк|\bакци",
    "speed_of_service": r"\bмедлен|\bждал|\bждать\b|\bочеред|\bдолго\b|\bожидан|\bподожд|\bзадерж|\bзатянул|\bтерпелив",
}

# --- Модели ---
MT_MODEL = "Helsinki-NLP/opus-mt-ru-en"
ABSA_MODEL = "yangheng/deberta-v3-base-absa-v1.1"
TRANSLATE_BATCH = 16