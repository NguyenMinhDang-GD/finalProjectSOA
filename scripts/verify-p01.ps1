$ErrorActionPreference = "Stop"

$Project = "pkb-test"
$ComposeFile = "docker-compose.test.yml"

Write-Host "=== P01 Isolated Verification Runner ===" -ForegroundColor Cyan

try {
    Write-Host "[1/4] Starting isolated test stack ($Project)..." -ForegroundColor Yellow
    docker compose -p $Project -f $ComposeFile up -d --build
    if ($LASTEXITCODE -ne 0) { throw "Failed to start isolated test stack" }

    Write-Host "[2/4] Waiting for test API Gateway health..." -ForegroundColor Yellow
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:18080/gateway-health" -TimeoutSec 3
            if ($resp.status -eq "ok") { $ready = $true; break }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $ready) { throw "Test API Gateway did not become healthy" }

    Write-Host "[3/4] Running T01-T14 reliability acceptance tests..." -ForegroundColor Yellow
    python tests/test_p01_reliability.py
    if ($LASTEXITCODE -ne 0) { throw "T01-T14 reliability tests failed" }

    Write-Host "[4/4] Running T15 main stack & build regression checks..." -ForegroundColor Yellow
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Main docker-compose.yml validation failed" }

    if (Test-Path frontend/node_modules) {
        Push-Location frontend
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
        } finally {
            Pop-Location
        }
    } else {
        docker build ./frontend
        if ($LASTEXITCODE -ne 0) { throw "Frontend Docker build failed" }
    }

    Write-Host "P01 VERIFICATION PASSED (T01-T15)" -ForegroundColor Green
} finally {
    Write-Host "Cleaning up isolated test project ($Project)..." -ForegroundColor Yellow
    docker compose -p $Project -f $ComposeFile down -v
}
