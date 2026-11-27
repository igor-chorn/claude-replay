# HOWTO

Все команды выполняются из корня репозитория, если не сказано иное.

## Как посмотреть дампы mitmproxy

Дамп — один на запуск: `logs/<run-id>/flows.mitm`.

Список дампов:

```bash
ls -lh logs/*/flows.mitm
```

Прочитать дамп (`-n` — не поднимать прокси, `-r` — читать файл):

```bash
uv run mitmdump -nr logs/<run-id>/flows.mitm
```

На каждый поток печатаются две строки: метод с URL и статус с размером ответа.

Только нужные потоки — фильтр последним аргументом:

```bash
uv run mitmdump -nr logs/<run-id>/flows.mitm "~u /v1/messages"
uv run mitmdump -nr logs/<run-id>/flows.mitm "~d api.anthropic.com & ~m POST"
```

| Фильтр | Отбирает по |
|---|---|
| `~u <regex>` | URL |
| `~d <regex>` | домену |
| `~m <метод>` | методу |
| `~c <код>` | статусу ответа |

Больше подробностей — `--flow-detail N`: 2 добавляет заголовки, 3 — тела
(обрезанные), 4 — тела целиком.

```bash
uv run mitmdump -nr logs/<run-id>/flows.mitm --flow-detail 3 "~u /v1/messages"
```

Начиная с уровня 2 на экран выводится токен из заголовка `authorization`.
Этот вывод никуда не копируйте.

Интерактивно, в браузере:

```bash
uv run mitmweb -n -r logs/<run-id>/flows.mitm
```

### Где ответ модели

Для `/v1/messages` mitmdump пишет `(content missing)`. SSE-ответы передаются
клиенту потоком, и mitmproxy их тело в дампе не хранит; аддон `tee_sse.py`
пишет его в `streams/<flow-id>.sse` — байт в байт как пришло по сети, то есть
сжатым gzip.

Найти файл ответа `/v1/messages` (у SSE-ответов MCP сжатия нет) и распаковать:

```bash
grep -l '"content_encoding": "gzip"' logs/<run-id>/streams/*.chunks.jsonl
gunzip -c logs/<run-id>/streams/<flow-id>.sse
```

Обзор запуска без секретов:

```bash
uv run tools/inventory logs/<run-id>
```

## Как записать запрос

Каждый запуск `claude -p` — реальный запрос к API.

### Одной командой

```bash
uv run tools/run_case --case A1 "Say hello."
uv run tools/inventory logs/<run-id>
```

`run_case` сам поднимает mitmdump, запускает `claude` в пустом каталоге вне
репозитория с минимальным окружением и останавливает прокси. Идентификатор
запуска (`<run-id>`) он печатает в конце.

- Порт по умолчанию 8080; если занят — `--port N`.
- Несколько промптов подряд — один сеанс: первый шаг новый, остальные идут с
  `--resume`:
  `uv run tools/run_case --case A1-A2 "Say hello." "Explain the Sieve of Eratosthenes."`
- Модель: `--model <имя>`.

Что остаётся в `logs/<run-id>/`:

| Файл | Содержимое |
|---|---|
| `manifest.json` | версии, флаги, промпты, время, коды выхода, вид авторизации |
| `flows.mitm` | все HTTP-потоки (запросы целиком; ответы, кроме SSE) |
| `streams/<flow-id>.sse` | сырые байты SSE-ответа (для `/v1/messages` — сжаты gzip) |
| `streams/<flow-id>.chunks.jsonl` | время, смещение и длина каждого куска |
| `steps/NN/stdout.jsonl` | вывод CLI в формате stream-json; ответ модели — в событии `result` |
| `steps/NN/stderr.txt` | stderr CLI |
| `mitmdump.log` | журнал прокси |

### По шагам, в двух терминалах

Терминал 1 — прокси:

```bash
mkdir -p logs/manual/streams
uv run mitmdump --listen-host 127.0.0.1 --listen-port 8080 \
    -w logs/manual/flows.mitm \
    -s tools/tee_sse.py --set tee_dir=logs/manual/streams
```

Терминал 2 — запрос:

```bash
mkdir -p logs/manual/steps/01
OUT="$PWD/logs/manual/steps/01"
TOOLS="$PWD/tools"
mkdir -p /tmp/claude-replay-scratch/manual && cd /tmp/claude-replay-scratch/manual
env -i HOME="$HOME" PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
    "$TOOLS/viamitm" -p 8080 -- \
    claude -p "Say hello." --output-format stream-json --verbose \
    > "$OUT/stdout.jsonl" 2> "$OUT/stderr.txt"
```

После ответа остановите прокси в первом терминале через Ctrl-C, иначе
`flows.mitm` не будет дописан.

На что обратить внимание:

- Каталог запуска `claude` должен быть вне репозитория: Claude Code читает
  `CLAUDE.md` из всех родительских каталогов, и текст попадёт в запрос.
- `env -i` не даёт окружению терминала протечь в записываемый сеанс.
- `uv run tools/inventory logs/manual` отработает, но вернёт код 1, потому что
  в ручном запуске нет `manifest.json`.

## Тесты

```bash
uv run pytest
```

Работают офлайн, на синтетических данных, API не трогают.

## Чего нельзя

Каталог `logs/` содержит токены, идентификаторы аккаунта и полные тела
запросов. Он исключён из git; не копируйте из него ничего в код, коммиты и
отчёты.
