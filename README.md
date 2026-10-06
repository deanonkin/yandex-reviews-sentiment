cat > README.md << 'EOF'
# yandex-reviews-sentiment

Анализ отзывов сети «Вкусно — и точка» с Яндекс.Карт:
парсинг → перевод RU→EN → аспектный анализ (ABSA) → Supabase → DataLens.

## Стек
Python, Playwright, Transformers (MarianMT, DeBERTa-ABSA), PostgreSQL (Supabase),
Docker, GitHub Actions.

## Запуск
```bash
python pipeline.py