# mc-lang-tool

Инструмент для массовой русификации модов Minecraft — извлекает `en_us.json` из `.jar` файлов, автоматически переводит через Google Translate и запаковывает обратно.

[English](#english) | [Русский](#русский)

---

## Русский

### Требования

- Python 3.10+
- Для автоперевода: `pip install deep-translator`

### Структура папок

```
project/
├── mc_lang_tool.py
├── translate_mc_langs.py
├── mods/          ← .jar файлы модов
├── output/        ← сюда unpack извлекает JSON (создаётся автоматически)
└── input/         ← сюда кладёшь переведённые папки для pack
```

### Шаг 1 — Извлечение (`mc_lang_tool.py unpack`)

Извлекает `en_us.json` из каждого `.jar` в папке `mods/` и раскладывает по папкам в `output/`.

```bash
# Базовое извлечение
python mc_lang_tool.py unpack

# Пропустить моды, в которых уже есть ru_ru.json
python mc_lang_tool.py unpack -skip=ru_ru

# Пропустить несколько локализаций
python mc_lang_tool.py unpack -skip=ru_ru,uk_ua

# Дополнительно извлечь ru_ru.json рядом с en_us.json (если есть в моде)
python mc_lang_tool.py unpack -ext=ru_ru

# Не задавать вопросов — автоматически пропускать проблемные моды
python mc_lang_tool.py unpack -non_ask

# Всё вместе
python mc_lang_tool.py unpack -non_ask -skip=ru_ru -ext=ru_ru
```

### Шаг 2 — Автоперевод (`translate_mc_langs.py`)

Переводит `en_us.json` в `ru_ru.json` во всех папках внутри `output/`. Уже переведённые ключи не трогает. Кэш сохраняется между запусками.

```bash
# Базовый перевод
python translate_mc_langs.py --root .\output\ --source en_us --target ru_ru

# Переводить также ключи, значение которых в ru_ru совпадает с en_us
# (когда кто-то скопировал en_us в ru_ru и не перевёл)
python translate_mc_langs.py --root .\output\ --source en_us --target ru_ru --retranslate-identical

# Перевести всё заново, игнорируя существующие ru_ru
python translate_mc_langs.py --root .\output\ --source en_us --target ru_ru --overwrite
```

После перевода в папке появится файл `mc_lang_translation_warnings.txt` — список ключей где переводчик потерял плейсхолдеры (`%s`, `§c` и т.д.) и перевод был откачен на оригинал. Таких строк обычно немного, их можно поправить вручную.

#### Все параметры `translate_mc_langs.py`

| Параметр | По умолчанию | Описание |
|---|---|---|
| `--root` | `.` | Папка для рекурсивного поиска |
| `--source` | `en_us` | Имя исходной локализации (без `.json`) |
| `--target` | `ru_ru` | Имя целевой локализации (без `.json`) |
| `--from-lang` | `en` | Язык источника для переводчика |
| `--to-lang` | `ru` | Язык перевода |
| `--retranslate-identical` | выкл | Переводить ключи, совпадающие с оригиналом |
| `--overwrite` | выкл | Перезаписать все существующие переводы |
| `--batch-size` | `150` | Интервал сохранения кэша (в строках) |
| `--max-chars` | `4500` | Макс. символов за один запрос к переводчику |
| `--retries` | `3` | Кол-во повторных попыток при ошибке |
| `--retry-sleep` | `2.0` | Задержка между попытками (сек) |
| `--cache` | `.mc_lang_translation_cache_ru.json` | Путь к файлу кэша |
| `--warnings` | `mc_lang_translation_warnings.txt` | Путь к файлу предупреждений |

### Шаг 3 — Запаковка (`mc_lang_tool.py pack`)

Берёт JSON файлы из папок в `input/` и запаковывает их обратно в соответствующие `.jar` в папке `mods/`.

```bash
# Базовая запаковка
python mc_lang_tool.py pack

# Пропустить моды, в которых уже есть ru_ru.json
python mc_lang_tool.py pack -skip=ru_ru

# Без вопросов
python mc_lang_tool.py pack -non_ask
```

Перед запаковкой переложи переведённые папки из `output/` в `input/` (или сразу работай с `output/` если структура совпадает).

### Типичный рабочий процесс

```
1. Положить .jar моды в папку mods/
2. python mc_lang_tool.py unpack -skip=ru_ru
3. python translate_mc_langs.py --root .\output\ --retranslate-identical
4. Вручную поправить строки из warnings.txt (их обычно немного)
5. Скопировать папки из output/ в input/
6. python mc_lang_tool.py pack
```

---

## English

### Requirements

- Python 3.10+
- For auto-translation: `pip install deep-translator`

### Folder structure

```
project/
├── mc_lang_tool.py
├── translate_mc_langs.py
├── mods/          ← .jar mod files
├── output/        ← unpack extracts JSON here (created automatically)
└── input/         ← place translated folders here for pack
```

### Step 1 — Extract (`mc_lang_tool.py unpack`)

Extracts `en_us.json` from each `.jar` in the `mods/` folder into per-mod folders in `output/`.

```bash
# Basic extraction
python mc_lang_tool.py unpack

# Skip mods that already have ru_ru.json
python mc_lang_tool.py unpack -skip=ru_ru

# Skip multiple locales
python mc_lang_tool.py unpack -skip=ru_ru,uk_ua

# Also extract ru_ru.json alongside en_us.json (if present in the mod)
python mc_lang_tool.py unpack -ext=ru_ru

# Non-interactive mode — skip problematic mods automatically
python mc_lang_tool.py unpack -non_ask

# All together
python mc_lang_tool.py unpack -non_ask -skip=ru_ru -ext=ru_ru
```

### Step 2 — Auto-translate (`translate_mc_langs.py`)

Translates `en_us.json` to `ru_ru.json` in all folders inside `output/`. Already translated keys are left untouched. The translation cache persists between runs.

```bash
# Basic translation
python translate_mc_langs.py --root ./output/ --source en_us --target ru_ru

# Also translate keys whose ru_ru value is identical to en_us
# (when someone copy-pasted en_us into ru_ru without translating)
python translate_mc_langs.py --root ./output/ --source en_us --target ru_ru --retranslate-identical

# Retranslate everything, ignoring existing ru_ru files
python translate_mc_langs.py --root ./output/ --source en_us --target ru_ru --overwrite
```

After translation, `mc_lang_translation_warnings.txt` will be created — it lists keys where the translator dropped placeholders (`%s`, `§c`, etc.) and the translation was safely rolled back to the original English. There are usually only a few of these and they can be fixed manually.

#### All `translate_mc_langs.py` options

| Option | Default | Description |
|---|---|---|
| `--root` | `.` | Folder to scan recursively |
| `--source` | `en_us` | Source locale name (without `.json`) |
| `--target` | `ru_ru` | Target locale name (without `.json`) |
| `--from-lang` | `en` | Translator source language |
| `--to-lang` | `ru` | Translator target language |
| `--retranslate-identical` | off | Retranslate keys identical to source |
| `--overwrite` | off | Overwrite all existing translations |
| `--batch-size` | `150` | Cache save interval (in strings) |
| `--max-chars` | `4500` | Max characters per translator request |
| `--retries` | `3` | Retry attempts on failure |
| `--retry-sleep` | `2.0` | Delay between retries (seconds) |
| `--cache` | `.mc_lang_translation_cache_ru.json` | Cache file path |
| `--warnings` | `mc_lang_translation_warnings.txt` | Warnings file path |

### Step 3 — Pack (`mc_lang_tool.py pack`)

Takes JSON files from folders in `input/` and packs them back into the matching `.jar` files in `mods/`.

```bash
# Basic pack
python mc_lang_tool.py pack

# Skip mods that already have ru_ru.json
python mc_lang_tool.py pack -skip=ru_ru

# Non-interactive mode
python mc_lang_tool.py pack -non_ask
```

Move the translated folders from `output/` to `input/` before packing (or use `output/` directly if the structure matches).

### Typical workflow

```
1. Put .jar mods into the mods/ folder
2. python mc_lang_tool.py unpack -skip=ru_ru
3. python translate_mc_langs.py --root ./output/ --retranslate-identical
4. Manually fix strings from warnings.txt (usually just a few)
5. Copy folders from output/ to input/
6. python mc_lang_tool.py pack
```

### Notes on warnings

The warnings file lists keys where placeholders were lost during translation. These are strings like:

- `%s`, `%1$s` — string format arguments (item names, counts)
- `§c`, `§e`, `&l` — Minecraft color/style codes
- `<unnamed>`, `<Shift for info>` — literal angle-bracket tokens

For these keys the script keeps the original English string rather than writing broken output that could crash the game. Fix them manually by opening the `ru_ru.json` next to `en_us.json` and restoring the placeholder in the correct position.

---

### License

MIT
