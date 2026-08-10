# Переезд на VPS

Инструкция для Ubuntu или Debian с доступом по SSH. Всё выполняется на сервере,
кроме шагов, помеченных **на компьютере**.

Замените `ВАШ_IP` на адрес сервера, а `ВАШ_ЮЗЕР` — на пользователя, под которым
вы заходите по SSH.

---

## 0. Перед началом — два обязательных дела

### Остановите бота на компьютере

Два запущенных экземпляра одного бота работать не могут: Telegram отдаёт
обновления только одному, второй получает ошибку `409 Conflict` и оба начинают
терять сообщения. Убедитесь, что локальный бот выключен, и больше его не
запускайте.

### Добавьте IP сервера в белый список FatSecret

Ключ FatSecret привязан к адресу. С компьютера он работал с `138.124.70.182`,
у сервера адрес другой — счётчик еды откажет сразу же.

Зайдите в кабинет на [platform.fatsecret.com](https://platform.fatsecret.com)
и внесите IP сервера в белый список. Узнать его на сервере:

```bash
curl ifconfig.me
```

Остальные функции бота от этого не зависят и будут работать в любом случае.

---

## 1. Подготовка сервера

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip sqlite3 rsync
```

Проверьте версию — нужна 3.10 или новее:

```bash
python3 --version
```

Отдельный пользователь для бота, без права входа в систему:

```bash
sudo useradd -r -m -d /opt/formabot -s /usr/sbin/nologin formabot
```

---

## 2. Копирование проекта

**На компьютере**, в PowerShell из папки проекта:

```powershell
scp -r bot deploy requirements.txt README.md selfcheck.py check_fatsecret.py check_food_ru.py ВАШ_ЮЗЕР@ВАШ_IP:/tmp/formabot
```

Затем **на сервере**:

```bash
sudo mkdir -p /opt/formabot
sudo cp -r /tmp/formabot/* /opt/formabot/
sudo rm -rf /tmp/formabot
```

Виртуальное окружение `.venv` не копируйте — оно собрано под Windows
и на Linux не заработает.

---

## 3. Перенос базы с данными

**На компьютере** уже лежит готовая чистая копия `formabot.backup.db`.
Отправьте её:

```powershell
scp formabot.backup.db ВАШ_ЮЗЕР@ВАШ_IP:/tmp/formabot.db
```

**На сервере**:

```bash
sudo mv /tmp/formabot.db /opt/formabot/formabot.db
```

Проверьте, что данные на месте:

```bash
sudo sqlite3 /opt/formabot/formabot.db "SELECT COUNT(*) FROM users;"
```

---

## 4. Настройки

Создайте `.env` **прямо на сервере** — так токен не пройдёт лишний раз
через сеть и не осядет в истории команд:

```bash
sudo -u formabot nano /opt/formabot/.env
```

Содержимое (значения возьмите из вашего локального `.env`):

```
BOT_TOKEN=
ADMIN_ID=
TZ=Europe/Moscow
FATSECRET_CLIENT_ID=
FATSECRET_CLIENT_SECRET=
```

Часовой пояс сервера менять не нужно: бот берёт `TZ` из этого файла и считает
все напоминания по нему, что бы ни стояло в системе.

Закройте файл от чужих глаз:

```bash
sudo chmod 600 /opt/formabot/.env
```

---

## 5. Окружение и зависимости

```bash
sudo chown -R formabot:formabot /opt/formabot
sudo -u formabot python3 -m venv /opt/formabot/.venv
sudo -u formabot /opt/formabot/.venv/bin/pip install --upgrade pip
sudo -u formabot /opt/formabot/.venv/bin/pip install -r /opt/formabot/requirements.txt
```

Проверка, что всё собралось (Telegram при этом не трогается):

```bash
cd /opt/formabot && sudo -u formabot .venv/bin/python selfcheck.py
```

Должно закончиться строкой `ВСЁ ПРОШЛО`.

Проверка ключей FatSecret — уже после того, как внесли IP в белый список:

```bash
cd /opt/formabot && sudo -u formabot .venv/bin/python check_fatsecret.py
```

---

## 6. Автозапуск

```bash
sudo cp /opt/formabot/deploy/formabot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now formabot
```

Проверьте:

```bash
systemctl status formabot
```

Живой лог:

```bash
journalctl -u formabot -f
```

В логе должна появиться строка `Запустился как @Treniroykabot`.

Теперь бот поднимается сам после перезагрузки сервера и после любого падения
(`Restart=always`, пауза 5 секунд).

---

## 7. Резервные копии

База лежит в одном файле, и потерять её легко. Поставьте ежедневную копию:

```bash
sudo chmod +x /opt/formabot/deploy/backup.sh
sudo crontab -e
```

Добавьте строку:

```
0 4 * * * /opt/formabot/deploy/backup.sh
```

Копии складываются в `/opt/formabot/backups`, старше 30 дней удаляются.
Раз в месяц скачивайте свежую копию к себе — сервер тоже может пропасть.

---

## Как обновлять бота дальше

После правок кода на компьютере:

```powershell
scp -r bot ВАШ_ЮЗЕР@ВАШ_IP:/tmp/bot
```

На сервере:

```bash
sudo rsync -a --delete /tmp/bot/ /opt/formabot/bot/
sudo chown -R formabot:formabot /opt/formabot/bot
sudo systemctl restart formabot
sudo rm -rf /tmp/bot
```

Если появились новые зависимости — сначала повторите шаг 5.

---

## Если что-то пошло не так

**Бот не стартует.** Смотрите причину:
`journalctl -u formabot -n 50 --no-pager`

**`409 Conflict` в логе.** Где-то запущен второй экземпляр — почти всегда это
забытый бот на компьютере.

**Счётчик еды отвечает про ключи.** IP сервера не в белом списке FatSecret,
либо провайдер сменил адрес. Проверьте `curl ifconfig.me` и сравните с кабинетом.

**Напоминания приходят не вовремя.** Проверьте `TZ` в `/opt/formabot/.env`
и перезапустите: `sudo systemctl restart formabot`.

**Права на файлы.** После любого копирования:
`sudo chown -R formabot:formabot /opt/formabot`
