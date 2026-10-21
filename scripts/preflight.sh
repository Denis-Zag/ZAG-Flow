#!/usr/bin/env sh
set -eu

BASE_URL=${BASE_URL:-http://127.0.0.1:8080}

printf "Проверка сайта: %s\n" "$BASE_URL"
curl --fail --silent --show-error "$BASE_URL/healthz"
printf "Проверка Backend API...\n"
curl --fail --silent --show-error "$BASE_URL/api/health"
printf "\nОсновные публичные точки доступны.\n"
