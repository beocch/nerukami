# nerukami: запуск сайта и фонового обработчика публикаций (Windows).
#
#   powershell -ExecutionPolicy Bypass -File run.ps1 [-Port 8000]
#
# Ctrl+C останавливает оба процесса.
param(
    [int]$Port = 8000,
    [string]$Address = '127.0.0.1'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    Write-Host 'Не найдено .venv. Сначала запустите install.ps1' -ForegroundColor Red
    exit 1
}

# Обработчик публикаций: отправляет запланированные посты в соцсети.
$worker = Start-Process -FilePath $Python -ArgumentList 'manage.py', 'run_studio_worker' -WorkingDirectory $Root -NoNewWindow -PassThru
Write-Host "Обработчик публикаций запущен (PID $($worker.Id))"
Write-Host "Сайт: http://${Address}:$Port/"

try {
    & $Python manage.py runserver "${Address}:$Port"
} finally {
    if (-not $worker.HasExited) {
        Stop-Process -Id $worker.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host 'Остановлено'
}
