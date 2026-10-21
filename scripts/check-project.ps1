$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Файл .env не найден. Скопируйте .env.example в .env и замените тестовые значения."
}

$forbiddenValues = @(
    "change_me_to_a_long_unique_password",
    "change_me_to_another_long_unique_password",
    "change_me_to_a_long_random_registry_secret"
)
$envContent = Get-Content -LiteralPath $envFile -Raw
foreach ($value in $forbiddenValues) {
    if ($envContent.Contains($value)) {
        throw "В .env осталось тестовое значение: $value"
    }
}

Push-Location $projectRoot
try {
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose обнаружил ошибку в конфигурации."
    }
    Write-Host "Конфигурация Docker Compose корректна."
}
finally {
    Pop-Location
}
