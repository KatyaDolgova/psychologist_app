# Структура проекта PsyConsult

Шпаргалка: где что лежит и куда идти, чтобы что-то поменять.

```
psychologist_app/
├── backend/          ← сервер на Python (FastAPI)
├── frontend-web/     ← веб-версия (React)
├── frontend/         ← мобильное приложение (React Native, Expo)
├── docs/             ← описание продукта (PRD.md), команды (TEAM.md), эта шпаргалка
├── .github/workflows ← CI: тесты и линтер (ci.yml), деплой (deploy.yml)
├── compose.yml       ← запуск всего проекта в Docker
├── .env              ← пароли и ключи (не в git, образец - .env.example)
└── Makefile          ← короткие команды: make start_dev, make ruff_check
```

## Запуск

```cmd
docker compose up -d
```

| Что | Адрес |
|---|---|
| Сайт | http://localhost:5173 |
| API и документация (Swagger) | http://localhost:8000/docs |
| PostgreSQL | порт 5432 |
| Redis | порт 6379 |

В корневом `.env` должно быть `STATIC_DIR=./backend/static`.

---

## Backend

Запрос проходит по слоям сверху вниз:

```
api/  →  services/  →  crud/  →  models/  →  база данных
          ↑ schemas/ описывают, какие данные приходят и уходят
```

| Папка | Что там | Когда туда идти |
|---|---|---|
| [main.py](../backend/main.py) | создание приложения, подключение Redis, раздача `/static` | меняется редко |
| [src/api/](../backend/src/api/) | **эндпоинты**, то есть адреса API | добавить или изменить адрес |
| [src/schemas/](../backend/src/schemas/) | **схемы Pydantic**: формат запросов и ответов, проверки данных | поменять поля или валидацию |
| [src/services/](../backend/src/services/) | **бизнес-логика** | изменить, что происходит при запросе |
| [src/crud/impl/](../backend/src/crud/impl/) | **запросы к базе** | добавить выборку или фильтр |
| [src/models/](../backend/src/models/) | **таблицы БД** (SQLAlchemy), в `enums/` - перечисления | добавить таблицу или колонку |
| [alembic/versions/](../backend/alembic/versions/) | **миграции БД** | после изменения моделей |
| [src/core/](../backend/src/core/) | JWT-токены, хеширование, подключение к БД и Redis, общие зависимости | - |
| [src/config/](../backend/src/config/) | [settings.py](../backend/src/config/settings.py) читает `.env`, плюс константы | новая переменная окружения |
| [src/utils/](../backend/src/utils/) | загрузка файлов, проверка телефона, коды подтверждения, SMS, звонки | - |
| [src/tasks/](../backend/src/tasks/) | задачи Celery: письма, SMS, слоты по расписанию | ⚠️ воркер Celery в `compose.yml` не запущен, задачи не выполняются |
| [tests/](../backend/tests/) | `unit/` - отдельные функции, `integration/` - API и сервисы | - |

### Адреса API

| Префикс | Файлы | Для чего |
|---|---|---|
| `/auth` | [api/auth.py](../backend/src/api/auth.py) → [auth_service.py](../backend/src/services/auth/auth_service.py) | вход по коду из письма, токены |
| `/user` | [api/users/user.py](../backend/src/api/users/user.py) → [user_service.py](../backend/src/services/user/user_service.py) | профиль клиента, анкета, аватар |
| `/user/psychologists` | [api/users/psychologists.py](../backend/src/api/users/psychologists.py) | список психологов для клиента |
| `/user/psychologists/favorites` | [api/users/favorites.py](../backend/src/api/users/favorites.py) | избранное |
| `/user/appointments` | [api/users/appointments.py](../backend/src/api/users/appointments.py) → [booking.py](../backend/src/services/availability/booking.py) | запись на слот, отмена, мои сессии |
| `/user/methods` | [api/users/payment_methods.py](../backend/src/api/users/payment_methods.py) | способы оплаты (СБП с SMS-кодом) |
| `/psychologists/profile` | [api/psychologists/profile.py](../backend/src/api/psychologists/profile.py) | профиль психолога: методы, цена, опыт |
| `/psychologists/template` | [working_hours.py](../backend/src/api/psychologists/working_hours.py) → [working_hours_service.py](../backend/src/services/working_hours_service.py) | шаблон рабочих часов |
| `/psychologists/slots` | [slots.py](../backend/src/api/psychologists/slots.py) → [slot_generation.py](../backend/src/services/availability/slot_generation.py), [slot_management.py](../backend/src/services/availability/slot_management.py) | генерация и ручное управление слотами |
| `/psychologists/{id}/free-slots` | [free_slots.py](../backend/src/api/psychologists/free_slots.py) | свободные слоты, которые видит клиент |
| `/psychologists/clients` | [clients.py](../backend/src/api/psychologists/clients.py), [client_notes.py](../backend/src/api/psychologists/client_notes.py) | клиенты психолога и заметки о них |
| `/psychologists/appointments` | [appointments.py](../backend/src/api/psychologists/appointments.py) | расписание психолога |
| `/chats` | [api/chats.py](../backend/src/api/chats.py) → [chats_service.py](../backend/src/services/chats/chats_service.py) | чаты и сообщения |
| WebSocket | [api/ws.py](../backend/src/api/ws.py) → [services/ws/](../backend/src/services/ws/) | сообщения в реальном времени |
| `/calls` | [api/calls.py](../backend/src/api/calls.py) → [call_service.py](../backend/src/services/call/call_service.py) | токены для видеозвонков LiveKit |
| `/admin` | [api/admin/](../backend/src/api/admin/) | админка: пользователи, группы |

### Таблицы БД ([src/models/](../backend/src/models/))

| Файл | Что хранит |
|---|---|
| [user.py](../backend/src/models/user.py) | аккаунт: email и роли |
| [client.py](../backend/src/models/client.py) | профиль клиента |
| [psychologist.py](../backend/src/models/psychologist.py) | профиль психолога |
| [psychologist_schedule.py](../backend/src/models/psychologist_schedule.py) | рабочие часы |
| [availability_slot.py](../backend/src/models/availability_slot.py) | слоты |
| [appointment.py](../backend/src/models/appointment.py) | записи на сессии |
| [chats.py](../backend/src/models/chats.py) | чаты и сообщения |
| [client_note.py](../backend/src/models/client_note.py) | заметки психолога о клиенте |
| [favorites.py](../backend/src/models/favorites.py) | избранное |
| [payment_method.py](../backend/src/models/payment_method.py) | способы оплаты |

---

## Веб-версия: [frontend-web/src/](../frontend-web/src/)

| Файл / папка | Что там |
|---|---|
| [main.tsx](../frontend-web/src/main.tsx), [app/App.tsx](../frontend-web/src/app/App.tsx) | точка входа |
| [app/routes.ts](../frontend-web/src/app/routes.ts) | **все страницы и кто их видит** |
| [api/](../frontend-web/src/api/) | запросы к бэкенду: `auth`, `profile`, `psychologist`, `chats`. В `client.ts` при ответе 401 происходит выход на страницу входа |
| [app/context/UserContext.tsx](../frontend-web/src/app/context/UserContext.tsx) | текущий пользователь и его роль |
| [app/types.ts](../frontend-web/src/app/types.ts) | типы данных |
| [app/components/ui/](../frontend-web/src/app/components/ui/) | готовые UI-элементы (кнопки, диалоги и т. д.), их обычно не трогают |
| [styles/](../frontend-web/src/styles/) | темы и стили Tailwind |

### Страницы ([app/components/](../frontend-web/src/app/components/))

| Адрес | Компонент | Кто видит |
|---|---|---|
| `/auth` | `Auth.tsx` | все: выбор роли и вход |
| `/` | `Dashboard.tsx` | психолог |
| `/clients`, `/clients/:id` | `Clients.tsx`, `ClientDetails.tsx` | психолог |
| `/working-hours` | `WorkingHours.tsx` | психолог |
| `/psychologists` | `Psychologists.tsx` (и запись на слот) | клиент |
| `/favorites` | `Favorites.tsx` | клиент |
| `/sessions` | `Sessions.tsx` | оба |
| `/chats` | `Chats.tsx` | оба |
| `/profile` | `Profile.tsx` | оба |

Меню и боковая панель - `Layout.tsx`. Доступ по ролям проверяют `ProtectedRoute.tsx` и `RoleRoute.tsx`.

---

## Мобильное приложение: [frontend/](../frontend/)

| Папка | Что там |
|---|---|
| `app/` | экраны: `auth`, `role`, `survey` (анкета), `psychologists`, `profile`, `groups`, `meditation`, `form` |
| `components/` | части экранов: чат, профиль, карточки психологов и т. д. |
| `api/` | запросы к бэкенду |
| `store/slices/` | состояние приложения (Redux): пользователь, чаты, сессии, группы |

---

## Куда идти, если нужно…

| Задача | Файлы |
|---|---|
| поменять поле в профиле клиента | `schemas/user.py` → `user_service.py` → `models/client.py` (+ миграция) → `Profile.tsx` |
| добавить новый адрес API | `api/…` → `services/…` → `crud/impl/…` |
| добавить колонку в БД | `models/…`, затем `docker exec backend alembic revision --autogenerate -m "описание"` |
| изменить страницу сайта | `frontend-web/src/app/components/<Страница>.tsx` |
| добавить страницу | компонент в `components/`, затем путь в `routes.ts` и пункт в `Layout.tsx` |
| запустить тесты | `docker exec backend python -m pytest` |
| проверить стиль кода | `make ruff_check` (или `make ruff_fix`, чтобы исправить автоматически) |

## Работа с git

Пушить напрямую в `main` нельзя, только через ветку и Pull Request:

```cmd
git checkout main
git pull
git checkout -b feature/название-задачи
git add <файлы>
git commit -m "описание изменений"
git push -u origin feature/название-задачи
```

Затем на GitHub создайте Pull Request в `main`.
