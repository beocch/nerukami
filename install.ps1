# nerukami: установка одной командой (Windows, PowerShell 5.1+). Без Docker, база SQLite.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# Ключи:
#   -NoAdmin   не спрашивать логин администратора (можно создать потом:
#              .venv\Scripts\python manage.py createsuperuser)
param(
    [switch]$NoAdmin
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$Root = $PSScriptRoot
Set-Location $Root

$TailwindVersion = '4.2.2'
$Python = Join-Path $Root '.venv\Scripts\python.exe'

function Step($n, $text) {
    Write-Host ''
    Write-Host "[$n/6] $text" -ForegroundColor Cyan
}

function Run($exe) {
    $cmdArgs = $args
    & $exe @cmdArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Команда завершилась с ошибкой ($LASTEXITCODE): $exe $($cmdArgs -join ' ')"
    }
}

function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @()
    if ($env:UV_INSTALL_DIR) { $candidates += (Join-Path $env:UV_INSTALL_DIR 'uv.exe') }
    if ($env:XDG_BIN_HOME) { $candidates += (Join-Path $env:XDG_BIN_HOME 'uv.exe') }
    $candidates += (Join-Path $HOME '.local\bin\uv.exe')
    $candidates += (Join-Path $HOME '.cargo\bin\uv.exe')
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

try {
    # 1. uv — менеджер Python от Astral
    Step 1 'Проверяю uv'
    $uv = Find-Uv
    if (-not $uv) {
        Write-Host 'uv не найден, ставлю официальным установщиком astral.sh'
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $uv = Find-Uv
        if (-not $uv) { throw 'uv установлен, но не найден. Откройте новое окно PowerShell и запустите install.ps1 снова' }
    }
    Write-Host "uv: $uv"

    # 2. Python 3.12 в .venv
    Step 2 'Готовлю Python 3.12 (.venv)'
    if (Test-Path $Python) {
        Write-Host '.venv уже есть'
    } else {
        Run $uv venv .venv --python 3.12
    }

    # 3. Зависимости
    Step 3 'Ставлю зависимости (requirements.txt)'
    Run $uv pip install --python $Python -r requirements.txt

    # 4. Настройки .env и база
    Step 4 'Настраиваю .env и базу данных'
    Run $Python scripts\setup_env.py
    Run $Python manage.py migrate --noinput

    # 5. Стили (Tailwind CSS, отдельный бинарник — Node.js не нужен)
    Step 5 'Собираю стили'
    $tools = Join-Path $Root '.tools'
    $tw = Join-Path $tools "tailwindcss-$TailwindVersion.exe"
    if (-not (Test-Path $tw)) {
        New-Item -ItemType Directory -Force $tools | Out-Null
        $url = "https://github.com/tailwindlabs/tailwindcss/releases/download/v$TailwindVersion/tailwindcss-windows-x64.exe"
        Write-Host "Скачиваю $url"
        Invoke-WebRequest -Uri $url -OutFile "$tw.part" -UseBasicParsing
        Move-Item "$tw.part" $tw -Force
    }
    Push-Location (Join-Path $Root 'theme\static_src')
    try {
        Run $tw -i ./src/styles.css -o ../static/css/dist/styles.css --minify
    } finally {
        Pop-Location
    }

    # 6. Администратор
    Step 6 'Администратор'
    if ($NoAdmin) {
        Write-Host 'Пропущено (-NoAdmin). Создать позже: .venv\Scripts\python manage.py createsuperuser'
    } else {
        Write-Host 'Придумайте почту и пароль для входа в nerukami'
        Run $Python manage.py createsuperuser
    }
} catch {
    Write-Host ''
    Write-Host "Установка остановилась: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host 'Готово.' -ForegroundColor Green
Write-Host 'Запуск:   powershell -ExecutionPolicy Bypass -File run.ps1'
Write-Host 'Адрес:    http://127.0.0.1:8000/'
Write-Host 'Остановить: Ctrl+C в окне, где запущен run.ps1'
