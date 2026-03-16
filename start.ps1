# =============================================================================
# start.ps1 - Kratos Data: One-shot launcher
# Starts PostgreSQL DB (first-run setup), FastAPI backend, and React frontend.
# Usage:  .\start.ps1              # normal start
#         .\start.ps1 -Seed        # also bulk-seed 4k parties / 6k accounts
#         .\start.ps1 -ResetDB     # drop + recreate DB, apply schema, seed demo
# =============================================================================
param(
    [switch]$Seed,      # run seed_bulk.py after schema setup
    [switch]$ResetDB    # wipe and recreate the database (destructive!)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- Resolve paths ---
$Root   = $PSScriptRoot
$Ui     = Join-Path $Root "ui"
$Python = "C:/Program Files/Python313/python.exe"
$Psql   = "C:/Program Files/PostgreSQL/18/bin/psql.exe"

# --- Read .env ---
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Error ".env not found at $EnvFile - copy .env.example and fill in your values."
}

$envVars = @{}
Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#]\S+=.+" } | ForEach-Object {
    $parts = $_ -split "=", 2
    $envVars[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
}

$DatabaseUrl = $envVars["DATABASE_URL"]
if (-not $DatabaseUrl -or $DatabaseUrl -like "*CHANGE_ME*") {
    Write-Error "DATABASE_URL in .env still has the placeholder value. Update it before starting."
}

# Parse psql-friendly values from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/dbname
$dbMatch = [regex]::Match($DatabaseUrl, "://(?<user>[^:]+):(?<pass>[^@]+)@(?<host>[^:/]+):?(?<port>\d*)/(?<db>.+)")
$DB_USER = $dbMatch.Groups["user"].Value
# URL-decode the password (e.g. %40 -> @, %25 -> %, etc.)
$DB_PASS = [System.Uri]::UnescapeDataString($dbMatch.Groups["pass"].Value)
$DB_HOST = $dbMatch.Groups["host"].Value
$DB_PORT = if ($dbMatch.Groups["port"].Value) { $dbMatch.Groups["port"].Value } else { "5432" }
$DB_NAME = $dbMatch.Groups["db"].Value

$env:PGPASSWORD = $DB_PASS   # lets psql authenticate without interactive prompt

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
}

function Invoke-Psql($sql) {
    & $Psql -U $DB_USER -h $DB_HOST -p $DB_PORT -c $sql 2>&1 | Out-Null
}

function Invoke-PsqlFile($file) {
    & $Psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -f $file
    if ($LASTEXITCODE -ne 0) { Write-Error "psql failed on $file" }
}

# --- Step 1: Database setup ---
Write-Step "1/4  Database setup"

# Check if DB exists
$dbExists = & $Psql -U $DB_USER -h $DB_HOST -p $DB_PORT `
    -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" postgres 2>&1

if ($ResetDB) {
    Write-Host "  [ResetDB] Dropping database $DB_NAME ..." -ForegroundColor Yellow
    Invoke-Psql "DROP DATABASE IF EXISTS $DB_NAME;"
    $dbExists = ""
}

if ($dbExists -notmatch "1") {
    Write-Host "  Creating database $DB_NAME ..."
    Invoke-Psql "CREATE DATABASE $DB_NAME;"

    Write-Host "  Applying schema (DDL) ..."
    Invoke-PsqlFile (Join-Path $Root "01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql")

    Write-Host "  Applying audit triggers ..."
    Invoke-PsqlFile (Join-Path $Root "04_AUDIT_TRIGGER.sql")

    Write-Host "  Loading demo seed data (5 accounts, 4 parties) ..."
    Invoke-PsqlFile (Join-Path $Root "03_SEED_DATA.sql")

    if ($Seed) {
        Write-Host "  Bulk seeding (4000 parties / 6000 accounts) - this takes ~30 s ..."
        & $Python (Join-Path $Root "seed_bulk.py")
        if ($LASTEXITCODE -ne 0) { Write-Error "seed_bulk.py failed" }
    }

    Write-Host "  Database ready." -ForegroundColor Green
} else {
    Write-Host "  Database '$DB_NAME' already exists - skipping schema/seed." -ForegroundColor Green
    if ($Seed) {
        Write-Host "  Running bulk seed on existing database ..."
        & $Python (Join-Path $Root "seed_bulk.py")
    }
}

# --- Step 2: Python dependencies ---
Write-Step "2/4  Python dependencies"
& $Python -m pip install -r (Join-Path $Root "requirements.txt") `
    --trusted-host pypi.org --trusted-host files.pythonhosted.org `
    --trusted-host pypi.python.org -q --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed" }
Write-Host "  Python packages OK." -ForegroundColor Green

# --- Step 3: Node dependencies ---
Write-Step "3/4  Node dependencies"
if (-not (Test-Path (Join-Path $Ui "node_modules"))) {
    Write-Host "  Running npm install ..."
    Push-Location $Ui
    npm install
    Pop-Location
    if ($LASTEXITCODE -ne 0) { Write-Error "npm install failed" }
} else {
    Write-Host "  node_modules already present - skipping npm install." -ForegroundColor Green
}

# --- Step 4: Launch backend + frontend ---
Write-Step "4/4  Launching services"

Write-Host ""
Write-Host "  Starting FastAPI backend  ->  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Starting React frontend   ->  http://localhost:5173" -ForegroundColor Yellow
Write-Host "  Swagger / API docs        ->  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Press Ctrl+C inside each window to stop." -ForegroundColor Gray
Write-Host ""

# Start backend in a new PowerShell window so it doesn't block
$backendCmd = "cd '$Root'; & '$Python' -m uvicorn main:app --reload --port 8000"
$backendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -PassThru

# Give uvicorn a moment to bind
Start-Sleep -Seconds 3

# Start frontend in another new PowerShell window
$frontendCmd = "cd '$Ui'; npm run dev"
$frontendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -PassThru

Write-Host "  Backend PID  : $($backendProc.Id)" -ForegroundColor Cyan
Write-Host "  Frontend PID : $($frontendProc.Id)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Both services are running in separate windows." -ForegroundColor Green
Write-Host "  Close those windows (or Ctrl+C inside them) to stop." -ForegroundColor Gray

# Open the UI in the default browser after a short delay
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"