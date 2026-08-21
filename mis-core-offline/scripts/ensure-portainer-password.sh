#!/usr/bin/env bash
# Garante uma credencial inicial nativa antes de o Compose iniciar o Portainer.

set -euo pipefail

ENV_FILE="${1:-.env}"

[ -f "$ENV_FILE" ] || {
  echo "ERRO: arquivo de ambiente nao encontrado: ${ENV_FILE}" >&2
  exit 1
}

env_value() {
  grep -E '^PORTAINER_ADMIN_PASSWORD=' "$ENV_FILE" \
    | head -n1 \
    | cut -d= -f2- \
    | tr -d '\r' || true
}

set_env_value() {
  local value="$1"
  if grep -q '^PORTAINER_ADMIN_PASSWORD=' "$ENV_FILE"; then
    sed -i "s|^PORTAINER_ADMIN_PASSWORD=.*|PORTAINER_ADMIN_PASSWORD=${value}|" "$ENV_FILE"
  else
    printf '\nPORTAINER_ADMIN_PASSWORD=%s\n' "$value" >>"$ENV_FILE"
  fi
}

generate_password() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 18
  else
    od -An -N18 -tx1 /dev/urandom | tr -d ' \n'
  fi
}

password="$(env_value)"
if [ -z "$password" ] || [[ "$password" == TROQUE* ]] || [[ "$password" == troque-* ]]; then
  password="$(generate_password)"
  set_env_value "$password"
  echo "  Senha inicial nativa do Portainer gerada no .env"
else
  echo "  Senha inicial nativa do Portainer preservada"
fi

chmod 600 "$ENV_FILE" 2>/dev/null || true
