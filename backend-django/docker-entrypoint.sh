#!/bin/bash
set -e

echo "🔄 Aguardando PostgreSQL..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 1
done
echo "✅ PostgreSQL está pronto!"

echo "🔄 Aplicando migrações..."
python manage.py migrate --noinput

echo "🔄 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "🔄 Criando superusuário (se não existir)..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser(
        username='$DJANGO_SUPERUSER_USERNAME',
        email='$DJANGO_SUPERUSER_EMAIL',
        password='$DJANGO_SUPERUSER_PASSWORD'
    )
    print('✅ Superusuário criado!')
else:
    print('ℹ️  Superusuário já existe.')
END

echo "🚀 Iniciando servidor Django..."
exec "$@"
