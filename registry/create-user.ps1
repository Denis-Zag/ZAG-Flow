param(
    [string]$RegistryUser = "zagflow"
)

$ErrorActionPreference = "Stop"
$authDirectory = Join-Path $PSScriptRoot "auth"
$authFile = Join-Path $authDirectory "htpasswd"

New-Item -ItemType Directory -Force -Path $authDirectory | Out-Null

$userInput = Read-Host "Имя пользователя Registry [$RegistryUser]"
if (-not [string]::IsNullOrWhiteSpace($userInput)) {
    $RegistryUser = $userInput.Trim()
}

$securePassword = Read-Host "Введите отдельный пароль Registry" -AsSecureString
$credential = [System.Management.Automation.PSCredential]::new($RegistryUser, $securePassword)
$plainPassword = $credential.GetNetworkCredential().Password

if ($plainPassword.Length -lt 12) {
    throw "Пароль должен содержать не менее 12 символов."
}

$content = $plainPassword | docker run --rm -i --entrypoint htpasswd httpd:2.4-alpine -Bni $RegistryUser
if ($LASTEXITCODE -ne 0) {
    throw "Docker не смог создать файл авторизации Registry."
}

$content | Set-Content -LiteralPath $authFile -Encoding ascii
$plainPassword = $null
Write-Host "Файл авторизации создан: $authFile"
