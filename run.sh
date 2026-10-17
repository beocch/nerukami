#!/usr/bin/env bash
# nerukami: запуск сайта и фонового обработчика публикаций (macOS / Linux).
#
#   bash run.sh [порт]
#
# Ctrl+C останавливает оба процесса.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PORT="${1:-8000}"
ADDRESS="${NERUKAMI_ADDRESS:-127.0.0.1}"
PY="$ROOT/.venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "Не найдено .venv. Сначала запустите install.sh" >&2
    exit 1
fi

# Обработчик публикаций: отправляет запланированные посты в соцсети.
"$PY" manage.py run_studio_worker &
WORKER=$!
trap 'kill "$WORKER" 2>/dev/null || true; echo "Остановлено"' EXIT
echo "Обработчик публикаций запущен (PID $WORKER)"
echo "Сайт: http://$ADDRESS:$PORT/"

"$PY" manage.py runserver "$ADDRESS:$PORT"
