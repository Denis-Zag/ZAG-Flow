#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
AUTH_DIR="$SCRIPT_DIR/auth"
AUTH_FILE="$AUTH_DIR/htpasswd"
REGISTRY_USER=${REGISTRY_USER:-zagflow}

mkdir -p "$AUTH_DIR"

printf "Имя пользователя Registry [%s]: " "$REGISTRY_USER"
read -r INPUT_USER
if [ -n "$INPUT_USER" ]; then
  REGISTRY_USER=$INPUT_USER
fi

printf "Введите отдельный пароль Registry: "
stty -echo
read -r REGISTRY_PASSWORD
stty echo
printf "\n"

if [ "${#REGISTRY_PASSWORD}" -lt 12 ]; then
  printf "Ошибка: пароль должен содержать не менее 12 символов.\n" >&2
  exit 1
fi

printf '%s\n' "$REGISTRY_PASSWORD" | docker run --rm -i \
  --entrypoint htpasswd httpd:2.4-alpine -Bni "$REGISTRY_USER" > "$AUTH_FILE"

chmod 600 "$AUTH_FILE"
printf "Файл авторизации создан: %s\n" "$AUTH_FILE"
