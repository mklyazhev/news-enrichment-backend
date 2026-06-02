# News Enrichment Backend

Backend-сервис для обогащения новостных карточек данными из HTML-страниц внешних новостных сайтов.

## Возможности

- хранение базовых новостных карточек: заголовок, источник, URL, дата публикации и анонс;
- запуск обогащения для одной новости, списка ID или новостей по критериям;
- фоновая обработка задач через Celery worker;
- парсинг HTML и извлечение полного текста, изображений, категорий, тегов, автора, счетчиков, keywords, summary и метаданных;
- API полной карточки новости для frontend-приложения;
- фильтрация и поиск по новостям;
- Swagger/OpenAPI: `/docs`, `/openapi.json`.

## Стек

- FastAPI
- SQLAlchemy AsyncSession + asyncpg
- PostgreSQL
- Alembic
- Celery
- Redis
- HTTPX + BeautifulSoup + lxml
- NLTK stopwords для частотного извлечения keywords из текста
- Pytest
- Docker Compose

## Источники

В качестве первого поддерживаемого источника выбран РИА Новости. Для `ria.ru` используется `RiaNewsParser`. Для остальных сайтов используется `GenericArticleParser`.

## Как работает обогащение

```text
POST /api/v1/enrichment/jobs
  -> FastAPI создает enrichment job в PostgreSQL
  -> FastAPI отправляет Celery task в Redis
  -> Celery worker забирает задачу
  -> worker выбирает нужные новости
  -> SourceParserRegistry выбирает RiaNewsParser или GenericArticleParser
  -> parser извлекает данные из HTML
  -> worker сохраняет enrichment-поля и обновляет job status
```

PostgreSQL хранит состояние: метаданные новости, поля для обогащения, статусы задач и ошибки. Redis используется как broker для Celery.

## Поля обогащения

Сервис сохраняет:

- `full_text` - полный текст статьи;
- `main_image_url` - основное изображение;
- `image_urls` - дополнительные изображения;
- `categories` - категории/рубрики;
- `tags` - теги;
- `author` - автор, если доступен;
- `views_count` - просмотры, если доступны в HTML;
- `comments_count` - комментарии, если доступны в HTML;
- `keywords` - ключевые слова;
- `summary` - description или первое предложение;
- `region`, `topic`, `has_video` - дополнительные метаданные;
- `parser_version`, `enriched_at`, `enrichment_error` - техническая информация об обогащении.

## Запуск через Docker Compose

```bash
docker compose up -d --build
```

Команда поднимает:

- `api` на `http://localhost:8000`;
- `worker` для Celery-задач;
- `postgres`;
- `redis`.

При старте API применяет миграции:

```bash
alembic upgrade head
```

Проверка доступности API:

```bash
curl http://localhost:8000/ping
```

Документация Swagger:

```text
http://localhost:8000/docs
```

## Примеры API

### Пинг

```http
GET /ping
```

### Создать базовую карточку

```http
POST /api/v1/news
```

```json
{
  "title": "Редкая \"голубая Луна\" взойдет 31 мая",
  "source": "РИА Новости",
  "source_url": "https://ria.ru/20260531/polnolunie-2095779946.html",
  "published_at": "2026-05-31T00:44:00+03:00",
  "teaser": "Второе полнолуние мая произойдет в последний день этого месяца."
}
```

### Запустить обогащение

```http
POST /api/v1/enrichment/jobs
```

```json
{
  "news_ids": [1],
  "only_missing": false
}
```

### Запустить обогащение по критериям

```http
POST /api/v1/enrichment/jobs
```

```json
{
  "source": "РИА Новости",
  "only_missing": true,
  "limit": 100
}
```

### Получить Job

```http
GET /api/v1/enrichment/jobs/{job_id}
```

### Получить полную карточку

```http
GET /api/v1/news/{news_id}
```

### Поиск и фильтрация

```http
GET /api/v1/news?q=Луна&source=РИА%20Новости&category=Наука&tag=Луна&enriched=true&limit=20&offset=0
```

## Тесты

```bash
pytest
```

В тестах есть fixture реальной HTML-страницы РИА: `tests/fixtures/ria.html`.
