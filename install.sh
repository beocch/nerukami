#!/usr/bin/env bash
# nerukami: установка одной командой (macOS / Linux). Без Docker, база SQLite.
#
#   bash install.sh            # с созданием администратора
#   bash install.sh --no-admin # без вопроса про администратора
set -euo pipefail

NO_ADMIN=0
for arg in "$@"; do
    case "$arg" in
        --no-admin) NO_ADMIN=1 ;;
        *) echo "Неизвестный ключ: $arg" >&2; exit 2 ;;
    esac
done

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

TAILWIND_VERSION="4.2.2"
PY="$ROOT/.venv/bin/python"

step() { printf '\n[%s/6] %s\n' "$1" "$2"; }
fail() { printf '\nУстановка остановилась: %s\n' "$1" >&2; exit 1; }
trap 'fail "команда на строке $LINENO завершилась с ошибкой"' ERR

find_uv() {
    if command -v uv >/dev/null 2>&1; then command -v uv; return; fi
    for c in "${UV_INSTALL_DIR:-}/uv" "${XDG_BIN_HOME:-}/uv" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$c" ]; then echo "$c"; return; fi
    done
}

# 1. uv
step 1 "Проверяю uv"
UV="$(find_uv || true)"
if [ -z "$UV" ]; then
    echo "uv не найден, ставлю официальным установщиком astral.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV="$(find_uv || true)"
    [ -n "$UV" ] || fail "uv установлен, но не найден. Откройте новый терминал и запустите install.sh снова"
fi
echo "uv: $UV"

# 2. Python 3.12
step 2 "Готовлю Python 3.12 (.venv)"
if [ -x "$PY" ]; then
    echo ".venv уже есть"
else
    "$UV" venv .venv --python 3.12
fi

# 3. Зависимости
step 3 "Ставлю зависимости (requirements.txt)"
"$UV" pip install --python "$PY" -r requirements.txt

# 4. .env и база
step 4 "Настраиваю .env и базу данных"
"$PY" scripts/setup_env.py
"$PY" manage.py migrate --noinput

# 5. Стили (отдельный бинарник Tailwind — Node.js не нужен)
step 5 "Собираю стили"
case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) TW_ASSET="tailwindcss-macos-arm64" ;;
    Darwin-x86_64) TW_ASSET="tailwindcss-macos-x64" ;;
    Linux-x86_64) TW_ASSET="tailwindcss-linux-x64" ;;
    Linux-aarch64|Linux-arm64) TW_ASSET="tailwindcss-linux-arm64" ;;
    *) fail "нет готового Tailwind для $(uname -s) $(uname -m)" ;;
esac
TW="$ROOT/.tools/tailwindcss-$TAILWIND_VERSION"
if [ ! -x "$TW" ]; then
    mkdir -p "$ROOT/.tools"
    URL="https://github.com/tailwindlabs/tailwindcss/releases/download/v$TAILWIND_VERSION/$TW_ASSET"
    echo "Скачиваю $URL"
    curl -fL "$URL" -o "$TW.part"
    chmod +x "$TW.part"
    mv "$TW.part" "$TW"
fi
(cd "$ROOT/theme/static_src" && "$TW" -i ./src/styles.css -o ../static/css/dist/styles.css --minify)

# 6. Администратор
step 6 "Администратор"
if [ "$NO_ADMIN" = 1 ]; then
    echo "Пропущено (--no-admin). Создать позже: .venv/bin/python manage.py createsuperuser"
else
    echo "Придумайте почту и пароль для входа в nerukami"
    "$PY" manage.py createsuperuser
fi

printf '\nГотово.\n'
echo "Запуск:     bash run.sh"
echo "Адрес:      http://127.0.0.1:8000/"
echo "Остановить: Ctrl+C в окне, где запущен run.sh"
