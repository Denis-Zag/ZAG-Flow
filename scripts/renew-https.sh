#!/bin/sh
# Проверить продление IP-сертификата и перечитать его в работающем Nginx.
set -eu

exec 9>/run/lock/zag-flow-certbot.lock
flock -n 9 || exit 0

docker run --rm --name zag-flow-certbot-renew \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/lib/letsencrypt:/var/www/certbot \
  -v /var/log/letsencrypt:/var/log/letsencrypt \
  certbot/certbot@sha256:f70ad0adbb7e117f0fe42a63c553f28ea451edabc0148757b6efcd9735acaa20 \
  renew --cert-name zag-flow-ip --non-interactive \
  --deploy-hook 'touch /var/www/certbot/.zag-flow-renewed' "$@"

if [ -f /var/lib/letsencrypt/.zag-flow-renewed ]; then
  cd /opt/zag-flow
  docker compose exec -T frontend nginx -t </dev/null
  docker compose exec -T frontend nginx -s reload </dev/null
  rm -f /var/lib/letsencrypt/.zag-flow-renewed
fi
