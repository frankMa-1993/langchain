# Start Postgres + Redis + Qdrant (Docker), install deps, run API.
# Run from repo root:  .\scripts\start-backend.ps1
# Worker must run separately:  arq app.workers.settings.WorkerSettings

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Test-Docker {
    return [bool](Get-Command docker -ErrorAction SilentlyContinue)
}

if (-not (Test-Docker)) {
    Write-Host ""
    Write-Host "未检测到 Docker CLI。最省事的做法：" -ForegroundColor Yellow
    Write-Host "  1) 安装 Docker Desktop（一次装好 PG + Redis + Qdrant）" -ForegroundColor White
    Write-Host "     winget install -e --id Docker.DockerDesktop" -ForegroundColor Cyan
    Write-Host "  2) 安装完成后重启电脑，打开 Docker Desktop 等其就绪" -ForegroundColor White
    Write-Host "  3) 再执行:  .\scripts\start-backend.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "若不想装 Docker：用云端数据库（见 README「无 Docker」），填好 .env 后只运行本脚本末尾的 venv + uvicorn。" -ForegroundColor DarkGray
    exit 1
}

Write-Host ">>> docker compose up -d" -ForegroundColor Green
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose 失败。请确认 Docker Desktop 已启动。" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ">>> 等待数据库就绪（约 5s）..." -ForegroundColor Green
Start-Sleep -Seconds 5

if (-not (Test-Path (Join-Path $ProjectRoot ".env"))) {
    Write-Host "未找到 .env，从 .env.example 复制..." -ForegroundColor Yellow
    Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $ProjectRoot ".env")
}

if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) {
    Write-Host ">>> python -m venv .venv" -ForegroundColor Green
    python -m venv (Join-Path $ProjectRoot ".venv")
}

$activate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
. $activate

Write-Host ">>> pip install -r requirements.txt" -ForegroundColor Green
python -m pip install -q -r requirements.txt

Write-Host ""
Write-Host "=== 基础设施与依赖已就绪 ===" -ForegroundColor Green
Write-Host "另开一个终端，在项目根目录执行（入库 Worker）：" -ForegroundColor White
Write-Host "  cd `"$ProjectRoot`"" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "  arq app.workers.settings.WorkerSettings" -ForegroundColor Cyan
Write-Host ""
Write-Host "当前窗口启动 API（Ctrl+C 停止）： http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
