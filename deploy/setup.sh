#!/bin/bash
# Установка ФормаБота на чистый VPS с Ubuntu или Debian.
# Запускать от root из распакованной папки:
#   bash deploy/setup.sh
#
# Скрипт можно запускать повторно — он не ломает то, что уже сделано.

set -euo pipefail

DIR=/opt/formabot
USER=formabot

say() { echo -e "\n\033[1;36m>>> $*\033[0m"; }
warn() { echo -e "\033[1;33m$*\033[0m"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Запускать нужно от root. Попробуйте: sudo bash deploy/setup.sh"
    exit 1
fi

if [ ! -d bot ] || [ ! -f requirements.txt ]; then
    echo "Не вижу папку bot и requirements.txt."
    echo "Запускайте скрипт из распакованной папки проекта."
    exit 1
fi

say "1/6 Ставлю системные пакеты"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip sqlite3 curl

PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python $PYV"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || {
    echo "Нужен Python 3.10 или новее, а стоит $PYV."
    echo "Возьмите образ поновее — Ubuntu 22.04 или 24.04."
    exit 1
}

say "2/6 Создаю пользователя $USER"
id -u "$USER" >/dev/null 2>&1 || useradd -r -m -d "$DIR" -s /usr/sbin/nologin "$USER"

say "3/6 Копирую файлы в $DIR"
mkdir -p "$DIR"
cp -r bot deploy requirements.txt "$DIR"/
for extra in README.md DEPLOY.md selfcheck.py check_fatsecret.py check_food_ru.py; do
    [ -f "$extra" ] && cp "$extra" "$DIR"/
done

# База переносится только если её ещё нет — чтобы повторный запуск
# скрипта не затёр данные, которые бот успел накопить.
if [ -f formabot.backup.db ] && [ ! -f "$DIR/formabot.db" ]; then
    cp formabot.backup.db "$DIR/formabot.db"
    echo "Перенёс базу с вашими данными."
elif [ -f "$DIR/formabot.db" ]; then
    warn "База на сервере уже есть — не трогаю её."
fi

say "4/6 Готовлю .env"
NEED_ENV=1
if [ -f "$DIR/.env" ] && grep -q '^BOT_TOKEN=.\+' "$DIR/.env"; then
    echo "Файл .env уже заполнен — оставляю как есть."
    NEED_ENV=0
else
    # Ищем готовый файл настроек, присланный с компьютера.
    for candidate in ./.env ./formabot.env /root/formabot.env /root/.env; do
        if [ -f "$candidate" ] && grep -q '^BOT_TOKEN=.\+' "$candidate"; then
            cp "$candidate" "$DIR/.env"
            echo "Взял настройки из $candidate"
            NEED_ENV=0
            break
        fi
    done
fi

if [ "$NEED_ENV" = "1" ]; then
    cat > "$DIR/.env" <<'EOF'
BOT_TOKEN=
ADMIN_ID=
TZ=Europe/Moscow
FATSECRET_CLIENT_ID=
FATSECRET_CLIENT_SECRET=
EOF
fi

# Ключи FatSecret временно гасим: пока IP сервера не в белом списке,
# заполненные ключи дают отказ на каждую запись еды, а пустые —
# понятное сообщение «счётчик пока не подключён».
if [ "${KEEP_FATSECRET:-0}" != "1" ]; then
    sed -i 's/^\(FATSECRET_[A-Z_]*\)=.*/\1=/' "$DIR/.env"
fi

chmod 600 "$DIR/.env"

say "5/6 Собираю окружение Python"
chown -R "$USER:$USER" "$DIR"
sudo -u "$USER" python3 -m venv "$DIR/.venv"
sudo -u "$USER" "$DIR/.venv/bin/pip" install --upgrade pip -q
sudo -u "$USER" "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"

say "6/6 Прописываю автозапуск"
cp "$DIR/deploy/formabot.service" /etc/systemd/system/
chmod +x "$DIR/deploy/backup.sh" 2>/dev/null || true
systemctl daemon-reload
systemctl enable formabot >/dev/null 2>&1

IP=$(curl -s --max-time 10 ifconfig.me || echo "не определился")

echo
echo "======================================================"
echo "  Установка закончена."
echo "======================================================"
echo
if [ "$NEED_ENV" = "1" ]; then
    echo "ОСТАЛОСЬ ОДНО ДЕЛО — заполнить настройки:"
    echo
    echo "  nano $DIR/.env"
    echo
    echo "Обязательны только две строки: BOT_TOKEN и ADMIN_ID."
    echo "Строки FATSECRET оставьте пустыми — бот запустится и без них,"
    echo "не будет работать только счётчик еды."
    echo "Сохранить: Ctrl+O, Enter, Ctrl+X."
    echo
    echo "Затем запустите бота:"
else
    echo "Запустить бота:"
fi

echo
echo "  systemctl start formabot"
echo "  journalctl -u formabot -f"
echo
echo "В логе должна появиться строка «Запустился как @...»."
echo "Выйти из просмотра лога — Ctrl+C, бот продолжит работать."
echo
echo "------------------------------------------------------"
echo "Когда доберётесь до FatSecret — внесите в белый список"
echo "в кабинете вот этот адрес: $IP"
echo "Потом впишите ключи в .env и перезапустите:"
echo "  systemctl restart formabot"
echo "------------------------------------------------------"
echo
