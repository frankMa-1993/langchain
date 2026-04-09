# ARQ ingest worker — run in a second terminal while API is up.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
. (Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1")
arq app.workers.settings.WorkerSettings
