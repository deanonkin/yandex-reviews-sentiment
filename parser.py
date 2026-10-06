"""Парсер отзывов с Яндекс.Карт через Playwright.

Запуск:
    python parser.py
Результат:
    data/reviews_raw.csv
"""
import asyncio
import sys

import nest_asyncio
import pandas as pd
from playwright.async_api import async_playwright

from config import (
    ESTABLISHMENTS, MAX_REVIEWS_PER_EST, PARSER_SLEEP_SEC,
    PARSER_HEADLESS, USER_AGENT, RAW_CSV,
)

nest_asyncio.apply()  # для работы в Colab / Jupyter


async def expand_all_reviews(page) -> int:
    """Кликает по всем кнопкам 'Показать полностью', чтобы раскрыть длинные отзывы."""
    selectors = [
        'button:has-text("Показать полностью")',
        'button:has-text("Показать целиком")',
        'span:has-text("Показать полностью")',
        'a:has-text("Показать полностью")',
    ]
    clicked = 0
    for sel in selectors:
        try:
            buttons = await page.locator(sel).all()
            for btn in buttons:
                try:
                    if await btn.is_visible():
                        await btn.click(timeout=1000)
                        clicked += 1
                except Exception:
                    pass
        except Exception:
            pass
    return clicked


async def parse_one(page, url: str, est_id: str, est_name: str,
                    max_reviews: int = MAX_REVIEWS_PER_EST) -> list[dict]:
    """Парсит отзывы с одной страницы заведения."""
    reviews = []
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(5_000)

    # Скроллим, чтобы подгрузить 50 отзывов
    for _ in range(8):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1_200)
        if await page.locator('[itemprop="review"]').count() >= max_reviews:
            break

    # Прокрутка вверх-вниз, чтобы все элементы отрисовались
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(1_000)
    for _ in range(5):
        await page.evaluate("window.scrollBy(0, 800)")
        await page.wait_for_timeout(500)

    clicked = await expand_all_reviews(page)
    print(f"  Раскрыто отзывов: {clicked}")
    await page.wait_for_timeout(2_000)

    blocks = await page.locator('[itemprop="review"]').all()
    for block in blocks[:max_reviews]:
        try:
            author = await block.locator('[itemprop="author"]').inner_text()
        except Exception:
            author = None
        try:
            r = await block.locator('[itemprop="ratingValue"]').get_attribute("content")
            rating = int(float(r))
        except Exception:
            rating = None
        try:
            text = await block.locator('[itemprop="reviewBody"]').inner_text()
        except Exception:
            text = None
        try:
            date = await block.locator('[itemprop="datePublished"]').get_attribute("content")
        except Exception:
            date = None

        reviews.append({
            "establishment_id": est_id,
            "establishment_name": est_name,
            "author": author,
            "rating": rating,
            "text": text,
            "date": date,
        })
    return reviews


async def parse_chain(establishments: list[dict]) -> list[dict]:
    """Парсит все заведения подряд, переиспользуя один браузер."""
    all_reviews = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=PARSER_HEADLESS)
        for i, est in enumerate(establishments, 1):
            print(f"\n[{i}/{len(establishments)}] {est['name']} ({est['id']})")
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            try:
                batch = await parse_one(page, est["url"], est["id"], est["name"])
                print(f"  ✓ Получено: {len(batch)}")
                all_reviews.extend(batch)
            except Exception as e:
                print(f"  ✗ Ошибка: {e}")
            await context.close()
            await asyncio.sleep(PARSER_SLEEP_SEC)
        await browser.close()
    return all_reviews


def main() -> None:
    reviews = asyncio.run(parse_chain(ESTABLISHMENTS))
    df = pd.DataFrame(reviews)
    df = df.drop_duplicates(
        subset=["establishment_id", "author", "text", "date"]
    ).reset_index(drop=True)

    df.to_csv(RAW_CSV, index=False, encoding="utf-8-sig")

    print(f"\n{'=' * 60}")
    print(f"ИТОГО: {len(df)} отзывов")
    print(f"По заведениям:")
    print(df.groupby("establishment_id").size())
    print(f"Распределение рейтингов:")
    print(df["rating"].value_counts().sort_index())
    print(f"\nCSV сохранён: {RAW_CSV}")


if __name__ == "__main__":
    main()