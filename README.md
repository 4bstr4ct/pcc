# High-Load Proxy Checker

Desktop-приложение для массовой проверки прокси-серверов с GUI на PyQt6.

---

## Структура проекта

```
Proxy/
  checker.py          — бэкенд: парсинг, проверка, GeoIP, спидтест
  main.py             — GUI: PyQt6 интерфейс, воркеры, главное окно
  requirements.txt    — зависимости Python
  dist/
    ProxyChecker.exe  — собранный исполняемый файл
```

---

## Установка и запуск

### Из исходников

```bash
pip install -r requirements.txt
python main.py
```

### Сборка .exe

```bash
python -m PyInstaller --noconfirm --onefile --windowed --name ProxyChecker main.py
```

Результат: `dist/ProxyChecker.exe`

---

## Зависимости

| Пакет          | Версия  | Назначение                       |
|----------------|---------|----------------------------------|
| PyQt6          | >= 6.5  | GUI-фреймворк                    |
| aiohttp        | >= 3.9  | Асинхронные HTTP-запросы         |
| aiohttp-socks  | >= 0.8  | SOCKS4/SOCKS5 через aiohttp     |

---

## Возможности

### Загрузка прокси

- **Ручной ввод** — формат `IP:PORT` или `IP:PORT:USER:PASS`
- **Из файла** — загрузка .txt файла
- **Из ссылки** — любой URL с текстовым списком прокси
- **GitHub-интеграция** — вставка ссылки на репозиторий/директорию GitHub автоматически ищет .txt файлы с прокси через GitHub API
- **Пресеты** — встроенные источники (TheSpeedX, proxifly, monosans, clarketm)

### Проверка

- **Протоколы**: SOCKS5, SOCKS4, HTTP, HTTPS, или "Все" (параллельная проверка всех)
- **Настраиваемый таймаут** — в миллисекундах (по умолчанию 350 мс)
- **Потоки** — от 1 до 500 параллельных проверок (по умолчанию 10)
- **Метод проверки** — запрос к `google.com/generate_204`, ожидание статуса 200/204
- **Режим "Все"** — пробует все 4 протокола параллельно, выбирает лучший по пингу

### Результаты

| Колонка   | Описание                                         |
|-----------|--------------------------------------------------|
| Страна    | Флаг + код страны (GeoIP через ip-api.com)       |
| Адрес     | IP:PORT                                          |
| Протокол  | Определённый протокол (цветовая маркировка)      |
| Авт.      | Логин или "Нет"                                  |
| Пинг (мс) | Время отклика (зелёный < 300, жёлтый < 1000, красный > 1000) |
| Скорость  | Кнопка "Тест" — скачивает ~1 MB через Cloudflare CDN |
| Действие  | Кнопка "В Telegram" — открывает tg://socks ссылку |

### Экспорт

- **Сохранить в TXT** — `IP:PORT` или `IP:PORT:USER:PASS`
- **Скопировать TG ссылки** — Telegram deep-links в буфер обмена

---

## Архитектура

### checker.py — бэкенд

| Компонент                   | Описание                                                      |
|-----------------------------|---------------------------------------------------------------|
| `Protocol`                  | Enum: HTTP, HTTPS, SOCKS4, SOCKS5                             |
| `Proxy`                     | Dataclass: ip, port, login, password, country, ping, speed    |
| `parse_proxies(text)`       | Парсит текст в список Proxy, дедупликация, валидация IP/порта |
| `parse_github_url(url)`     | Классифицирует GitHub URL (repo/dir/file), извлекает owner/repo/branch |
| `search_github_proxy_files` | Ищет .txt файлы с прокси в GitHub-репозитории через API       |
| `github_to_raw(url)`        | Конвертирует blob/raw GitHub URL в raw.githubusercontent.com  |
| `check_single_proxy`        | Проверяет один прокси одним протоколом, измеряет пинг         |
| `check_all_protocols`       | Проверяет прокси всеми протоколами параллельно, выбирает лучший |
| `lookup_geoip(ip)`          | GeoIP через ip-api.com (страна, код)                          |
| `speed_test_proxy`          | Скачивает ~1 MB через прокси, возвращает скорость в KB/s      |
| `CheckerEngine`             | Оркестратор: семафор, воркеры, GeoIP, сортировка по пингу     |

### main.py — GUI

| Компонент               | Описание                                                 |
|-------------------------|----------------------------------------------------------|
| `CheckerWorker`         | QThread — запуск CheckerEngine в фоне                    |
| `UrlLoaderWorker`       | QThread — загрузка прокси по URL                         |
| `GithubSearchWorker`    | QThread — поиск файлов в GitHub-репозитории              |
| `MultiUrlLoaderWorker`  | QThread — пакетная загрузка нескольких URL               |
| `SpeedTestWorker`       | QThread — тест скорости одного прокси                    |
| `MainWindow`            | Главное окно: левая панель (настройки), правая (таблица) |
| `PROXY_SOURCES`         | Словарь пресетов: название → raw URL                     |
| `DARK_STYLE`            | Catppuccin Mocha тема (QSS)                              |

### Потоки данных

```
Загрузка:
  URL/файл/пресет → parse_proxies() → QTextEdit

Проверка:
  QTextEdit → parse_proxies() → CheckerEngine → [check_single_proxy | check_all_protocols]
    → on_result (каждый валидный) → таблица (в реальном времени)
    → lookup_geoip (пакетно) → on_finished → пересортировка таблицы

Спидтест:
  Кнопка "Тест" → SpeedTestWorker → speed_test_proxy → результат в ячейку

GitHub-поиск:
  URL репозитория → parse_github_url → GithubSearchWorker → search_github_proxy_files
    → диалог выбора → MultiUrlLoaderWorker → QTextEdit
```

---

## Внешние API

| API                    | Использование           | Лимиты                          |
|------------------------|-------------------------|---------------------------------|
| ip-api.com             | GeoIP (страна по IP)    | 45 запросов/мин (бесплатно)     |
| api.github.com         | Поиск файлов в репо     | 60 запросов/час без токена      |
| speed.cloudflare.com   | Тест скорости (~1 MB)   | Без ограничений                 |
| google.com/generate_204| Проверка доступности    | Без ограничений                 |

---

## Цветовая схема

Тема: **Catppuccin Mocha**

| Элемент         | Цвет    | Hex     |
|-----------------|---------|---------|
| Фон             | Base    | #1e1e2e |
| Поля ввода      | Surface0| #313244 |
| Кнопки          | Blue    | #89b4fa |
| Стоп            | Red     | #f38ba8 |
| Экспорт         | Green   | #a6e3a1 |
| Telegram        | Mauve   | #cba6f7 |
| Тест скорости   | Yellow  | #f9e2af |
| SOCKS5          | Blue    | #89b4fa |
| SOCKS4          | Sky     | #89dceb |
| HTTP            | Green   | #a6e3a1 |
| HTTPS           | Teal    | #94e2d5 |
| Пинг < 300мс    | Green   | #a6e3a1 |
| Пинг < 1000мс   | Yellow  | #f9e2af |
| Пинг > 1000мс   | Red     | #f38ba8 |
