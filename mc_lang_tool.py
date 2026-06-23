"""
mc_lang_tool.py — инструмент для распаковки и запаковки en_us.json из .jar модов Minecraft.

Использование:
  python mc_lang_tool.py unpack              — достаёт en_us.json из модов в ./mods → ./output/<имя_мода>/
  python mc_lang_tool.py pack               — берёт JSON из ./input/<имя_мода>/ и пакует обратно в ./mods/<имя_мода>.jar
  python mc_lang_tool.py unpack -skip=ru_ru — пропускает моды, в которых уже есть ru_ru.json
  python mc_lang_tool.py unpack -skip=ru_ru,be_be  — можно указать несколько локализаций через запятую
  python mc_lang_tool.py unpack -ext=ru_ru  — достаёт en_us.json и ru_ru.json, если ru_ru есть в моде
"""

import sys
import os
import zipfile
import shutil
import glob

MODS_DIR   = "mods"
OUTPUT_DIR = "output"
INPUT_DIR  = "input"

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def print_header(text: str):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

def print_ok(text: str):
    print(f"  {GREEN}✔{RESET}  {text}")

def print_warn(text: str):
    print(f"  {YELLOW}⚠{RESET}  {text}")

def print_err(text: str):
    print(f"  {RED}✘{RESET}  {text}")

def print_info(text: str):
    print(f"  {CYAN}→{RESET}  {text}")


def normalize_locale_list(raw: str) -> list[str]:
    locales: list[str] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if not entry.endswith(".json"):
            entry += ".json"
        locales.append(entry.lower())
    return locales


def parse_args() -> tuple[str, list[str], bool, list[str]]:
    """
    Разбирает аргументы командной строки.
    Возвращает (команда, список локализаций для пропуска, флаг non_ask).
    Формат: mc_lang_tool.py <unpack|pack> [-skip=loc1,loc2,...] [-non_ask]
    """
    if len(sys.argv) < 2 or sys.argv[1] not in ("unpack", "pack"):
        print(f"{BOLD}Использование:{RESET}")
        print(f"  python mc_lang_tool.py {GREEN}unpack{RESET} [-skip=<локализация,...>] [-ext=<локализация,...>] [-non_ask]")
        print(f"  python mc_lang_tool.py {GREEN}pack{RESET}   [-skip=<локализация,...>] [-non_ask]")
        print()
        print(f"  {YELLOW}-skip{RESET} — пропускать моды, в которых уже есть указанная локализация.")
        print(f"  Можно указать несколько через запятую: {YELLOW}-skip=ru_ru,be_be{RESET}")
        print(f"  {YELLOW}-ext{RESET} — дополнительно извлекать указанную локализацию рядом с en_us.json.")
        print(f"  {YELLOW}-non_ask{RESET} — не запрашивать действия, автоматически пропускать проблемные моды.")
        print()
        print(f"  Примеры:")
        print(f"    python mc_lang_tool.py unpack -skip=ru_ru")
        print(f"    python mc_lang_tool.py unpack -ext=ru_ru")
        print(f"    python mc_lang_tool.py pack   -skip=be_be,uk_ua")
        print(f"    python mc_lang_tool.py unpack -non_ask")
        sys.exit(1)

    command = sys.argv[1]
    skip_locales: list[str] = []
    extra_locales: list[str] = []
    non_ask = False

    for arg in sys.argv[2:]:
        if arg.startswith("-skip="):
            raw = arg[len("-skip="):]
            skip_locales.extend(normalize_locale_list(raw))
        elif arg.startswith("-ext="):
            raw = arg[len("-ext="):]
            extra_locales.extend(normalize_locale_list(raw))
        elif arg == "-non_ask":
            non_ask = True
        else:
            print_warn(f"Неизвестный аргумент: {arg} (игнорирую)")

    extra_locales = sorted(set(extra_locales))
    return command, skip_locales, non_ask, extra_locales


def has_skip_locale(zf: zipfile.ZipFile, skip_locales: list[str]) -> str | None:
    """
    Проверяет наличие любой из локализаций в архиве.
    Возвращает имя найденного файла (например 'ru_ru.json') или None.
    """
    for name in zf.namelist():
        basename = os.path.basename(name).lower()
        if basename in skip_locales:
            return basename
    return None

def find_json_in_zip(zf: zipfile.ZipFile, target_name: str) -> str | None:
    """Ищет файл с данным именем (без пути) внутри zip. Возвращает полный внутренний путь или None."""
    for name in zf.namelist():
        if os.path.basename(name).lower() == target_name.lower():
            return name
    return None


def ask_alternative_json(zf: zipfile.ZipFile, jar_path: str) -> str | None:
    """
    Когда en_us.json не найден — предлагает пользователю выбор:
      s  — пропустить мод
      <имя файла> — ввести другое название JSON
    Возвращает внутренний путь к выбранному файлу или None (пропустить).
    """
    # Покажем все JSON внутри архива, чтобы пользователю было проще
    json_files = [n for n in zf.namelist() if n.endswith(".json")]
    if json_files:
        print(f"\n  {YELLOW}JSON-файлы найденные в архиве:{RESET}")
        for jf in json_files:
            print(f"      {jf}")
    else:
        print(f"\n  {YELLOW}В архиве нет ни одного .json файла.{RESET}")

    print(f"\n  Введите название нужного JSON (например: ru_ru.json)")
    print(f"  или нажмите Enter / введите 's' чтобы пропустить:")

    while True:
        answer = input("  > ").strip()
        if answer == "" or answer.lower() == "s":
            return None

        found = find_json_in_zip(zf, answer)
        if found:
            print_ok(f"Найден: {found}")
            return found
        else:
            print_warn(f"Файл '{answer}' не найден в архиве. Попробуйте ещё раз.")


def extract_json_file(zf: zipfile.ZipFile, internal_path: str, out_dir: str, target_filename: str | None = None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    if target_filename is None:
        target_filename = os.path.basename(internal_path)
    out_file = os.path.join(out_dir, target_filename)
    with zf.open(internal_path) as src, open(out_file, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return out_file


def unpack(skip_locales: list[str] = [], non_ask: bool = False, extra_locales: list[str] = []):
    print_header("UNPACK — извлечение JSON из модов")
    if skip_locales:
        print_info(f"Пропуск модов с локализациями: {', '.join(skip_locales)}\n")
    if extra_locales:
        print_info(f"Доп. локализации для извлечения: {', '.join(extra_locales)}\n")
    if non_ask:
        print_info("Режим без запросов: проблемные моды пропускаются автоматически\n")

    if not os.path.isdir(MODS_DIR):
        print_err(f"Папка '{MODS_DIR}' не найдена. Создайте её и положите туда .jar файлы.")
        sys.exit(1)

    jar_files = glob.glob(os.path.join(MODS_DIR, "*.jar"))
    if not jar_files:
        print_warn(f"В папке '{MODS_DIR}' нет .jar файлов.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total   = len(jar_files)
    success = 0
    skipped = 0

    for i, jar_path in enumerate(sorted(jar_files), 1):
        mod_name = os.path.splitext(os.path.basename(jar_path))[0]
        print(f"[{i}/{total}] {BOLD}{mod_name}{RESET}")
        print_info(f"Обрабатываю: {jar_path}")

        try:
            with zipfile.ZipFile(jar_path, "r") as zf:
                # Проверяем skip-локализации
                if skip_locales:
                    found_skip = has_skip_locale(zf, skip_locales)
                    if found_skip:
                        print_warn(f"Найдена локализация {found_skip} — пропускаю.\n")
                        skipped += 1
                        continue

                internal_path = find_json_in_zip(zf, "en_us.json")

                if internal_path is None:
                    print_warn("en_us.json не найден в архиве.")

                    if non_ask:
                        print_warn("Пропускаю мод (режим -non_ask).\n")
                        skipped += 1
                        continue

                    print(f"\n  Выберите действие:")
                    print(f"  [1] Указать другой JSON")
                    print(f"  [2] Пропустить этот мод")

                    while True:
                        choice = input("  > ").strip()
                        if choice == "2" or choice.lower() in ("", "s"):
                            print_warn("Пропускаю мод.\n")
                            skipped += 1
                            break
                        elif choice == "1":
                            internal_path = ask_alternative_json(zf, jar_path)
                            if internal_path is None:
                                print_warn("Пропускаю мод.\n")
                                skipped += 1
                            else:
                                # Извлекаем выбранный файл
                                out_dir = os.path.join(OUTPUT_DIR, mod_name)
                                target_filename = os.path.basename(internal_path)
                                out_file = extract_json_file(zf, internal_path, out_dir, target_filename)
                                print_ok(f"Извлечено → {out_file}\n")
                                success += 1
                            break
                        else:
                            print_warn("Введите 1 или 2.")
                else:
                    out_dir = os.path.join(OUTPUT_DIR, mod_name)
                    out_file = extract_json_file(zf, internal_path, out_dir, "en_us.json")
                    print_ok(f"Извлечено ({internal_path}) → {out_file}")
                    for extra_locale in extra_locales:
                        extra_path = find_json_in_zip(zf, extra_locale)
                        if extra_path is None:
                            print_warn(f"{extra_locale} не найден, оставляю только en_us.json.")
                            continue
                        extra_out = extract_json_file(zf, extra_path, out_dir, extra_locale)
                        print_ok(f"Извлечено ({extra_path}) → {extra_out}")
                    print()
                    success += 1

        except zipfile.BadZipFile:
            print_err(f"Файл повреждён или не является ZIP-архивом. Пропускаю.\n")
            skipped += 1
        except Exception as e:
            print_err(f"Ошибка: {e}. Пропускаю.\n")
            skipped += 1

    print(f"\n{BOLD}Готово:{RESET} {GREEN}{success} извлечено{RESET}, {YELLOW}{skipped} пропущено{RESET} из {total} модов.")


# ---------------------------------------------------------------------------
# PACK
# ---------------------------------------------------------------------------

def pack(skip_locales: list[str] = [], non_ask: bool = False):
    print_header("PACK — запаковка JSON обратно в моды")
    if skip_locales:
        print_info(f"Пропуск модов с локализациями: {', '.join(skip_locales)}\n")
    if non_ask:
        print_info("Режим без запросов: проблемные моды пропускаются автоматически\n")

    if not os.path.isdir(INPUT_DIR):
        print_err(f"Папка '{INPUT_DIR}' не найдена. Создайте её и положите папки с JSON файлами.")
        sys.exit(1)

    if not os.path.isdir(MODS_DIR):
        print_err(f"Папка '{MODS_DIR}' не найдена.")
        sys.exit(1)

    mod_dirs = [
        d for d in os.listdir(INPUT_DIR)
        if os.path.isdir(os.path.join(INPUT_DIR, d))
    ]

    if not mod_dirs:
        print_warn(f"В папке '{INPUT_DIR}' нет подпапок с модами.")
        return

    total   = len(mod_dirs)
    success = 0
    skipped = 0

    for i, mod_name in enumerate(sorted(mod_dirs), 1):
        print(f"[{i}/{total}] {BOLD}{mod_name}{RESET}")

        # Ищем jar в mods/ с именем, совпадающим с папкой (без учёта расширения)
        jar_path = os.path.join(MODS_DIR, mod_name + ".jar")
        if not os.path.isfile(jar_path):
            # Попробуем найти файл, у которого имя начинается с mod_name
            candidates = glob.glob(os.path.join(MODS_DIR, mod_name + "*.jar"))
            if len(candidates) == 1:
                jar_path = candidates[0]
                print_warn(f"Точного совпадения нет, использую: {os.path.basename(jar_path)}")
            elif len(candidates) > 1:
                if non_ask:
                    print_warn(f"Найдено несколько подходящих .jar — пропускаю (режим -non_ask).\n")
                    skipped += 1
                    continue

                print_warn(f"Найдено несколько подходящих .jar:")
                for c in candidates:
                    print(f"      {c}")
                print_warn("Укажите полное имя файла (без пути) или 's' для пропуска:")
                while True:
                    answer = input("  > ").strip()
                    if answer.lower() == "s" or answer == "":
                        jar_path = None
                        break
                    candidate = os.path.join(MODS_DIR, answer)
                    if os.path.isfile(candidate):
                        jar_path = candidate
                        break
                    print_warn("Файл не найден, попробуйте ещё раз.")
                if jar_path is None:
                    print_warn("Пропускаю.\n")
                    skipped += 1
                    continue
            else:
                print_err(f".jar для '{mod_name}' не найден в '{MODS_DIR}'. Пропускаю.\n")
                skipped += 1
                continue

        # Проверяем skip-локализации
        if skip_locales:
            try:
                with zipfile.ZipFile(jar_path, "r") as zf:
                    found_skip = has_skip_locale(zf, skip_locales)
                    if found_skip:
                        print_warn(f"Найдена локализация {found_skip} — пропускаю.\n")
                        skipped += 1
                        continue
            except zipfile.BadZipFile:
                pass  # ошибка всплывёт ниже при реальной обработке

        # Собираем список JSON файлов из input/<mod_name>/
        input_mod_dir = os.path.join(INPUT_DIR, mod_name)
        json_files = glob.glob(os.path.join(input_mod_dir, "*.json"))

        if not json_files:
            print_warn(f"В папке {input_mod_dir} нет .json файлов. Пропускаю.\n")
            skipped += 1
            continue

        print_info(f"Цель: {jar_path}")
        print_info(f"JSON файлов для запаковки: {len(json_files)}")

        try:
            # Определяем внутренний путь на основе en_us.json в архиве
            with zipfile.ZipFile(jar_path, "r") as zf:
                en_us_internal = find_json_in_zip(zf, "en_us.json")
                if en_us_internal:
                    lang_dir_internal = en_us_internal.rsplit("/", 1)[0] if "/" in en_us_internal else ""
                else:
                    # Если en_us.json не было — кладём в assets/modid/lang/
                    # попробуем угадать из структуры архива
                    assets_dirs = [
                        n for n in zf.namelist()
                        if n.startswith("assets/") and "/lang/" in n
                    ]
                    if assets_dirs:
                        lang_dir_internal = assets_dirs[0].rsplit("/", 1)[0] if "/" in assets_dirs[0] else ""
                    else:
                        lang_dir_internal = "assets/unknown/lang"
                    print_warn(f"en_us.json не найден в архиве, буду класть в: {lang_dir_internal}/")

            # Читаем весь архив в память
            tmp_path = jar_path + ".tmp"
            with zipfile.ZipFile(jar_path, "r") as zf_in, \
                 zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:

                # Имена файлов которые мы будем заменять/добавлять
                files_to_inject: dict[str, str] = {}  # internal_path -> local_path
                for jf in json_files:
                    fname = os.path.basename(jf)
                    internal = lang_dir_internal + "/" + fname if lang_dir_internal else fname
                    files_to_inject[internal] = jf

                # Копируем все файлы кроме тех, что заменяем
                replaced = set()
                for item in zf_in.infolist():
                    if item.filename in files_to_inject:
                        replaced.add(item.filename)
                    else:
                        zf_out.writestr(item, zf_in.read(item.filename))

                # Вписываем наши JSON (и новые, и заменённые)
                for internal_path, local_path in files_to_inject.items():
                    with open(local_path, "rb") as f:
                        data = f.read()
                    zf_out.writestr(internal_path, data)
                    action = "заменён" if internal_path in replaced else "добавлен"
                    print_ok(f"{os.path.basename(local_path)} → {internal_path} ({action})")

            # Заменяем оригинальный jar
            os.replace(tmp_path, jar_path)
            print_ok(f"Архив обновлён: {jar_path}\n")
            success += 1

        except zipfile.BadZipFile:
            print_err(f"Файл повреждён или не является ZIP-архивом. Пропускаю.\n")
            if os.path.exists(jar_path + ".tmp"):
                os.remove(jar_path + ".tmp")
            skipped += 1
        except Exception as e:
            print_err(f"Ошибка: {e}. Пропускаю.\n")
            if os.path.exists(jar_path + ".tmp"):
                os.remove(jar_path + ".tmp")
            skipped += 1

    print(f"\n{BOLD}Готово:{RESET} {GREEN}{success} запаковано{RESET}, {YELLOW}{skipped} пропущено{RESET} из {total} модов.")


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    command, skip_locales, non_ask, extra_locales = parse_args()
    if command == "unpack":
        unpack(skip_locales, non_ask, extra_locales)
    elif command == "pack":
        pack(skip_locales, non_ask)

if __name__ == "__main__":
    main()
