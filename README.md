# Предсказания 🔮

Система рыночных предсказаний с ML-прогнозами, мини-играми и NFT.

## Стек
- **FastAPI** — REST API (`/api/v1`)
- **Streamlit** — MVP личный кабинет
- **Supabase** — PostgreSQL + Auth + RLS
- **scikit-learn** — ML модели (StackingRegressor + LogisticRegression)
- **yfinance / MOEX** — источники рыночных данных
- **Cloudflare R2** — хранение артефактов

## ML — результаты обучения
| Цель | Метрика | Значение |
|---|---|---|
| `target_r1` (1-day return) | MAE | 0.00050 |
| `target_R20` (20-day return) | MAE | 0.00093 |
| `target_p1_up` (direction 1d) | ROC-AUC | **0.990** |
| `target_p20_up` (direction 20d) | ROC-AUC | **0.984** |

Обучено на 15 тикерах × 7 лет (24 231 сэмплов, 17 признаков).

## Быстрый старт

```bash
# 1. Зависимости
pip install -r requirements.txt

# 2. Обучить модели
python scripts/train_now.py

# 3. API
uvicorn src.api.main:app --reload

# 4. Streamlit ЛК
streamlit run src/app_streamlit/Home.py
```

## Структура

```
src/
  api/          # FastAPI — 8 роутеров
  app_streamlit/ # 7 страниц (Home + Forecasts/News/Games/Spin/Snake/NFT/Wallet)
  etl/          # Загрузка данных MOEX / yfinance
  features/     # Фичи (RSI, MACD, ATR, rolling returns)
  models/       # ML пайплайн
  wallet/       # Дебит/кредит + RPC-защита от race condition
  spin/         # SpinEngine (HMAC-SHA256, provably fair)
  nft/          # NFT mint/burn/transfer
scripts/
  train_now.py  # Standalone обучение
data/
  artifacts/    # Обученные модели (.pkl) + train_summary.json
db/
  schema.sql    # DDL всех таблиц
  rls.sql       # Row Level Security политики
.github/
  workflows/
    ci.yml      # Lint + test на каждый push
    nightly.yml # Ночной ETL → train → upload (02:00 UTC)
```

## Конфигурация

Скопируй `.env.example` → `.env` и заполни:
```
SUPABASE_URL=
SUPABASE_KEY=
R2_BUCKET=
R2_ENDPOINT=
R2_KEY=
R2_SECRET=
```

## CI/CD
- **ci.yml** — `ruff` lint + `pytest tests/` на каждый PR
- **nightly.yml** — скачка данных → переобучение → загрузка артефактов на R2

## Лицензия
MIT
