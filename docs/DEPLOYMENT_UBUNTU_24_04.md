# Развёртывание ZAG Flow на Ubuntu 24.04

## Проверенная конфигурация

Проект фактически развёрнут на Timeweb Cloud:

- Ubuntu 24.04 LTS, `amd64`;
- 2 vCPU;
- 4 ГБ RAM и 2 ГБ swap;
- диск 30 ГБ;
- публичный IPv4;
- вход пользователя `root` с локального компьютера по SSH-ключу;
- каталог проекта `/opt/zag-flow`.

В учебном задании указана Ubuntu 22.04. Для развёртывания выбрана более новая LTS-версия Ubuntu 24.04, которая поддерживается Docker и имеет более длительный жизненный цикл.

## Сетевой контур

В UFW открыты только:

| Порт | Доступ | Назначение |
|---|---|---|
| `22/tcp` | публично | SSH по ключу |
| `80/tcp` | публично | учебный HTTP до подключения TLS |

Порты `5050`, `5432`, `5000` и `8000` наружу не открываются. pgAdmin и авторизованный Registry проверяются через SSH-туннель. Порт `443/tcp` следует открыть только одновременно с настройкой TLS.

## 1. Подключение по SSH

```bash
ssh -i PATH_TO_PRIVATE_KEY root@SERVER_IP
```

После первого входа:

```bash
apt update
apt upgrade -y
```

Проверка системы:

```bash
lsb_release -a
uname -m
```

## 2. Установка Docker из официального репозитория

```bash
apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

Проверка:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

## 3. Swap и firewall

Для сервера с 4 ГБ RAM настроено 2 ГБ swap как страховка при сборке образов. После успешной проверки SSH-входа по ключу включается firewall:

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw --force enable
ufw status verbose
```

## 4. Подготовка проекта

Исходники размещаются в `/opt/zag-flow`. После получения проекта:

```bash
cd /opt/zag-flow
cp .env.example .env
chmod 600 .env
```

В `.env` задаётся `HTTP_PORT=80`. Для PostgreSQL, pgAdmin и Registry используются разные случайные значения. Пример генерации:

```bash
openssl rand -base64 36
```

Секреты не отправляются в чат, не добавляются в Git и не повторяются между сервисами.

Создание пользователя Registry:

```bash
chmod +x registry/create-user.sh scripts/preflight.sh
./registry/create-user.sh
```

Файл `registry/auth/htpasswd` должен иметь права `600` и не попадать в Git.

## 5. Запуск и проверка

```bash
cd /opt/zag-flow
docker compose config --quiet
docker compose up -d --build
docker ps
docker compose logs --tail 100
BASE_URL=http://127.0.0.1 ./scripts/preflight.sh
```

Дополнительные проверки с VPS:

```bash
curl -fsS http://127.0.0.1/api/health
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/v2/
```

Для `/v2/` без авторизации ожидается `401 Unauthorized`: Registry доступен, но закрыт паролем.

## 6. Доступ к pgAdmin

Порт pgAdmin публикуется только на localhost VPS. На рабочем компьютере создаётся SSH-туннель:

```bash
ssh -i PATH_TO_PRIVATE_KEY -L 5050:127.0.0.1:5050 root@SERVER_IP
```

После этого pgAdmin открывается по адресу `http://127.0.0.1:5050`. В VS Code Remote-SSH тот же результат можно получить через вкладку `PORTS`, перенаправив порт `5050`.

Для подключения pgAdmin к PostgreSQL внутри Compose используются:

- host: `postgres`;
- port: `5432`;
- database: значение `POSTGRES_DB`;
- username: значение `POSTGRES_USER`;
- password: значение `POSTGRES_PASSWORD`.

## 7. Безопасная проверка Registry

До появления HTTPS учётные данные Registry нельзя отправлять по открытому интернет-соединению. Для учебной проверки перенаправляется порт Nginx `80` через Remote-SSH, после чего локально открывается `/v2/` и выполняется авторизация.

Успешный ответ Registry:

```json
{}
```

## 8. TLS перед реальной эксплуатацией

До подключения TLS разрешён только учебный HTTP-запуск с вымышленными данными. Для реальной эксплуатации необходимы домен или иной способ выпуска доверенного сертификата, HTTPS и обновлённые правила firewall.

## Остановка

```bash
cd /opt/zag-flow
docker compose down
```

Именованные тома сохраняются. Команда `docker compose down -v` используется только при осознанном удалении тестовых данных.
