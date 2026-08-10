#!/bin/bash
# Обновление бота до свежей версии с GitHub.
#
# Запуск от root из любого места:
#   bash /root/formabot/deploy/update.sh
#
# Зачем отдельный скрипт: репозиторий лежит в /root/formabot, а работает бот
# из /opt/formabot. Просто "git pull" в рабочем каталоге не сработает —
# там нет .git. Этот скрипт делает всё в правильном порядке.

set -euo pipefail

SRC=${SRC:-/root/formabot}
DIR=/opt/formabot
USER=formabot

say() { echo -e "\n\033[1;36m>>> $*\033[0m"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Запускать от root: sudo bash $0"
    exit 1
fi

if [ ! -d "$SRC/.git" ]; then
    echo "Не нашёл репозиторий в $SRC."
    echo "Если клонировали в другое место, укажите его:"
    echo "  SRC=/путь/к/formabot bash $0"
    exit 1
fi

say "1/4 Забираю свежий код"
cd "$SRC"
git pull

say "2/4 Обновляю файлы бота"
# Копируем только код. Файл .env и база остаются нетронутыми.
cp -r bot deploy requirements.txt "$DIR"/
for extra in README.md DEPLOY.md selfcheck.py check_fatsecret.py check_food_ru.py; do
    [ -f "$extra" ] && cp "$extra" "$DIR"/
done
chown -R "$USER:$USER" "$DIR/bot" "$DIR/deploy"

say "3/4 Догоняю зависимости"
sudo -u "$USER" "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"

say "4/4 Перезапускаю"
cp -f "$DIR/deploy/formabot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl restart formabot

sleep 3
echo
if systemctl is-active --quiet formabot; then
    echo "Бот обновлён и работает."
    echo
    journalctl -u formabot -n 5 --no-pager | tail -3
else
    echo "Бот НЕ поднялся. Смотрите причину:"
    echo "  journalctl -u formabot -n 30 --no-pager"
    exit 1
fi
