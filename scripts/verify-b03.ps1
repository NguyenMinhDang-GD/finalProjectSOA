$ErrorActionPreference = "Stop"

Write-Host "=== B03 Isolated Verification Runner ===" -ForegroundColor Cyan

Push-Location "$PSScriptRoot\..\frontend"
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Pop-Location

Push-Location "$PSScriptRoot\.."
docker compose config --quiet
docker compose -f docker-compose.test.yml config --quiet
docker compose -f docker-compose.prod.yml config --quiet

try {
    docker compose -p pkb-test -f docker-compose.test.yml up -d --build --wait
    python tests/test_p01_reliability.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python tests/test_b01_concurrency_security.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python tests/test_b02_financial_lifecycle.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python tests/test_b02_v_acceptance.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python tests/test_b03_business_operations.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python tests/test_b03_v_acceptance.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    docker compose -p pkb-test -f docker-compose.test.yml down -v --remove-orphans
    Pop-Location
}
