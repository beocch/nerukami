# nerukami

**nerukami** («не руками») — программа, которая готовит, планирует и публикует посты в соцсети:
Instagram, YouTube, TikTok, Facebook, Threads и другие. Ставится на свой компьютер, работает в браузере.
Посты можно делать вручную в интерфейсе или поручить ИИ-агенту (например, Claude Code) через MCP.

nerukami — форк [BrightBean Studio](https://github.com/brightbeanxyz/brightbean-studio)
(лицензия AGPL-3.0). Почти всё, что умеет программа, сделано авторами BrightBean Studio.
Исходное английское описание с полной документацией лежит в [README.upstream.md](README.upstream.md).

## Что добавлено по сравнению с BrightBean Studio

| Что | Статус |
|---|---|
| **Пробные Reels в Instagram** (trial reels: ролик сначала показывают тем, кто на вас не подписан). Включается в редакторе поста, через REST API и через MCP (параметр `instagram_trial`: `MANUAL` или `SS_PERFORMANCE`) | готово |
| **Публикация в Instagram с локального компьютера** без туннеля (ngrok, cloudflared): видео загружается в Instagram напрямую, а не по ссылке | в работе |
| **Установка одной командой** без Docker и PostgreSQL: SQLite, Python ставится сам | готово |
| **MCP для Claude Code** — инструкция на русском: [docs/ru/claude-code-mcp.md](docs/ru/claude-code-mcp.md) | готово |

## Установка

Нужен только интернет. Docker, PostgreSQL и Node.js не нужны.

**Windows.** Скачайте проект (зелёная кнопка Code → Download ZIP) и распакуйте. Откройте папку,
в адресной строке Проводника наберите `powershell` и нажмите Enter. В открывшемся окне:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

**macOS / Linux.** В терминале, в папке проекта:

```bash
bash install.sh
```

Что делает установщик:

1. Ставит [uv](https://docs.astral.sh/uv/) (менеджер Python), если его нет.
2. Создаёт папку `.venv` с Python 3.12 и ставит зависимости из `requirements.txt`.
3. Создаёт файл настроек `.env`: база SQLite (`db.sqlite3`), случайные `SECRET_KEY` и `ENCRYPTION_KEY_SALT`.
4. Создаёт таблицы в базе.
5. Собирает стили (скачивает готовую программу Tailwind CSS в папку `.tools`).
6. Спрашивает почту и пароль администратора. Пропустить: `-NoAdmin` (Windows) или `--no-admin`.

Повторный запуск безопасен: существующий `.env` и база не затираются.

## Запуск

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1      # Windows
```

```bash
bash run.sh                                           # macOS / Linux
```

Откройте в браузере <http://127.0.0.1:8000/>. Вместе с сайтом запускается обработчик публикаций
(`manage.py run_studio_worker`) — без него запланированные посты не уйдут. Остановить оба: Ctrl+C.
Другой порт: `run.ps1 -Port 8100` или `bash run.sh 8100`.

Чтобы подключить соцсети, нужны ключи приложений каждой платформы. Как их получить — в разделе
[Platform Credentials](README.upstream.md#platform-credentials) исходного README. Ключи вписываются в `.env`.

## Поддерживаемые платформы

| Платформа | Публикация | Комментарии | Личные сообщения | Статистика |
|---|:---:|:---:|:---:|:---:|
| Facebook | ✓ | ✓ | ✓ | ✓ |
| Instagram (через Facebook) | ✓ | ✓ | ✓ | ✓ |
| Instagram (напрямую) | ✓ | ✓ | ✓ | ✓ |
| LinkedIn (личный профиль) | ✓ | ✓ | — | ✓ |
| LinkedIn (страница компании) | ✓ | ✓ | — | ✓ |
| TikTok | ✓ | — | — | ✓ |
| YouTube | ✓ | ✓ | — | ✓ |
| Pinterest | ✓ | — | — | ✓ |
| Threads | ✓ | ✓ | — | ✓ |
| Bluesky | ✓ | ✓ | — | — |
| Google Business Profile | ✓ | — | — | ✓ |
| Mastodon | ✓ | ✓ | — | — |
| DEV.to | ✓ | — | — | — |

## Название программы

Название, которое видно в интерфейсе, в MCP и в документации API, задаётся переменной `APP_NAME`
в `.env` (по умолчанию `nerukami`).

## Лицензия

AGPL-3.0, как и у BrightBean Studio — см. [LICENSE](LICENSE). Если вы даёте доступ к изменённой
версии программы другим людям по сети, вы обязаны дать им и её исходный код.

Основано на [BrightBean Studio](https://github.com/brightbeanxyz/brightbean-studio).
