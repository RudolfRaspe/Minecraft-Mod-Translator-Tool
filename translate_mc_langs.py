#!/usr/bin/env python3
"""
Batch-translates Minecraft lang JSON files while preserving keys, order,
formatting codes, and placeholders.

Example:
  python translate_mc_langs.py --root . --source en_us --target ru_ru
  python translate_mc_langs.py --root "C:/mods/langs" --overwrite
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from deep_translator import GoogleTranslator


PROTECTED_RE = re.compile(
    r"(§[0-9A-FK-ORa-fk-or]|&[0-9A-FK-ORa-fk-or]|"
    r"%(\d+\$)?[-#+ 0,(<]*\d*(\.\d+)?[bcdeEfFgGosxXaAtT%]|"
    r"\{[A-Za-z0-9_.:-]+(?:,[^{}]*)?\}|"
    r"\$\{[^{}]+\}|"
    r"<[^<>\n]+>|"
    r"\\[nrtbf\"\\/])"
)

KEY_NAME_RE = re.compile(
    r"^(mouse\.[A-Za-z0-9_.-]+|key\.[A-Za-z0-9_.-]+|[A-Z0-9_ +./:-]{1,16})$"
)


def load_json_pairs(path: Path) -> list[tuple[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=list)


def safe_load_json_pairs(path: Path) -> list[tuple[str, Any]]:
    """Читает JSON-файл как список пар. При ошибке парсинга печатает предупреждение и возвращает []."""
    try:
        return load_json_pairs(path)
    except json.JSONDecodeError as e:
        print(f"  [WARN] Невалидный JSON, пропускаю файл: {path}\n         {e}", file=sys.stderr)
        return []
    except OSError as e:
        print(f"  [WARN] Не удалось прочитать файл: {path}\n         {e}", file=sys.stderr)
        return []


def dump_json_pairs(pairs: list[tuple[str, Any]]) -> str:
    lines = ["{"]
    for index, (key, value) in enumerate(pairs):
        comma = "," if index < len(pairs) - 1 else ""
        lines.append(
            f"  {json.dumps(key, ensure_ascii=False)}: "
            f"{json.dumps(value, ensure_ascii=False)}{comma}"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def load_cache(path: Path) -> dict[str, str]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, cache: dict[str, str]) -> None:
    path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def protect(text: str) -> tuple[str, list[str]]:
    protected: list[str] = []

    def repl(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f" __MC_PH_{len(protected) - 1}__ "

    return PROTECTED_RE.sub(repl, text), protected


def unprotect(text: str, protected: list[str]) -> str:
    for index, value in enumerate(protected):
        text = text.replace(f"__MC_PH_{index}__", value)
        text = text.replace(f"__MC_PH_ {index}__", value)
        text = text.replace(f"__MC_PH {index}__", value)
    return re.sub(r" {2,}", " ", text)


def prepare_value(value: str) -> tuple[str, str, str, list[str]] | None:
    if not value or not value.strip():
        return None

    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    core = value.strip()

    # Do not translate raw key names/buttons that are intentionally literal.
    if KEY_NAME_RE.fullmatch(core):
        return None

    masked, protected = protect(core)
    return leading, trailing, masked, protected


def finish_value(prepared: tuple[str, str, str, list[str]], translated: str | None) -> str:
    leading, trailing, masked, protected = prepared
    if translated is None:
        translated = masked
    translated = unprotect(str(translated), protected).strip()
    return f"{leading}{translated}{trailing}"


def tokens(text: str) -> list[str]:
    return [match.group(0) for match in PROTECTED_RE.finditer(text)]


def missing_tokens(source: str, translated: str) -> list[str]:
    missing: list[str] = []
    remaining = translated
    for token in tokens(source):
        if token in remaining:
            remaining = remaining.replace(token, "", 1)
        else:
            missing.append(token)
    return missing


def translate_text(
    translator: GoogleTranslator,
    text: str,
    retries: int,
    retry_sleep: float,
) -> str | None:
    for attempt in range(retries + 1):
        try:
            translated = translator.translate(text)
            return translated if translated is not None else text
        except Exception as exc:
            if attempt >= retries:
                print(f"  translate failed after retries: {exc}", file=sys.stderr)
                return None
            time.sleep(retry_sleep * (attempt + 1))
    return None


def translate_many(
    values: list[str],
    translator: GoogleTranslator,
    max_chars: int,
    retries: int,
    retry_sleep: float,
) -> dict[str, str]:
    prepared: dict[str, tuple[str, str, str, list[str]]] = {}
    result: dict[str, str] = {}

    for value in values:
        item = prepare_value(value)
        if item is None:
            result[value] = value
        else:
            prepared[value] = item

    chunk: list[str] = []
    chunk_chars = 0

    def flush() -> None:
        nonlocal chunk, chunk_chars
        if not chunk:
            return

        source_lines = [prepared[value][2] for value in chunk]
        translated_text = translate_text(
            translator, "\n".join(source_lines), retries, retry_sleep
        )
        lines = translated_text.splitlines() if translated_text is not None else []

        if len(lines) != len(chunk):
            lines = [
                translate_text(translator, prepared[value][2], retries, retry_sleep)
                for value in chunk
            ]

        for value, translated in zip(chunk, lines):
            candidate = finish_value(prepared[value], translated)
            if missing_tokens(value, candidate):
                # Last resort: translate the unmasked string. If that still
                # damages placeholders, keep the original instead of breaking MC.
                raw = translate_text(translator, value, retries, retry_sleep)
                candidate = raw if raw and not missing_tokens(value, raw) else value
            result[value] = candidate

        chunk = []
        chunk_chars = 0

    for value in prepared:
        masked = prepared[value][2]
        extra = len(masked) + 1
        if chunk and chunk_chars + extra > max_chars:
            flush()
        chunk.append(value)
        chunk_chars += extra
    flush()

    return result


def missing_source_keys(
    source_path: Path,
    target_path: Path,
    retranslate_identical: bool = False,
) -> list[str]:
    if not target_path.exists():
        return [key for key, _value in load_json_pairs(source_path)]

    source_pairs = load_json_pairs(source_path)
    target_pairs = safe_load_json_pairs(target_path)

    source_by_key: dict[str, str] = {k: v for k, v in source_pairs if isinstance(v, str)}
    target_by_key: dict[str, list[str]] = {}
    for key, value in target_pairs:
        target_by_key.setdefault(key, []).append(value)

    # Счётчик для дедупликации дублирующихся ключей
    target_counts: dict[str, int] = {k: len(v) for k, v in target_by_key.items()}

    missing: list[str] = []
    for key, source_value in source_pairs:
        if target_counts.get(key, 0) > 0:
            target_counts[key] -= 1
            if retranslate_identical and isinstance(source_value, str):
                # Берём первое совпадающее значение из target
                target_values = target_by_key.get(key, [])
                idx = len(target_values) - target_counts.get(key, 0) - 1
                target_value = target_values[idx] if idx < len(target_values) else None
                if target_value == source_value:
                    missing.append(key)
        else:
            missing.append(key)
    return missing


def collect_values(
    files: list[Path],
    cache: dict[str, str],
    target_name: str,
    overwrite: bool,
    retranslate_identical: bool = False,
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()

    for path in files:
        target_path = path.with_name(target_name)
        missing_keys = set() if overwrite else set(
            missing_source_keys(path, target_path, retranslate_identical)
        )

        for key, value in load_json_pairs(path):
            needs_translation = overwrite or not target_path.exists() or key in missing_keys
            if (
                needs_translation
                and isinstance(value, str)
                and value not in cache
                and value not in seen
            ):
                seen.add(value)
                values.append(value)

    return values


def build_target_pairs(
    source_path: Path,
    target_path: Path,
    cache: dict[str, str],
    overwrite: bool,
    retranslate_identical: bool = False,
) -> list[tuple[str, Any]]:
    source_pairs = load_json_pairs(source_path)
    if overwrite or not target_path.exists():
        return [
            (key, cache.get(value, value) if isinstance(value, str) else value)
            for key, value in source_pairs
        ]

    target_pairs = safe_load_json_pairs(target_path)
    target_by_key: dict[str, list[tuple[int, Any]]] = {}
    for index, (key, value) in enumerate(target_pairs):
        target_by_key.setdefault(key, []).append((index, value))

    used_target_indices: set[int] = set()
    merged_pairs: list[tuple[str, Any]] = []

    for key, source_value in source_pairs:
        existing_values = target_by_key.get(key, [])
        if existing_values:
            index, target_value = existing_values.pop(0)
            used_target_indices.add(index)
            if (
                retranslate_identical
                and isinstance(source_value, str)
                and isinstance(target_value, str)
                and target_value == source_value
            ):
                # Значение идентично source — подставляем перевод из кэша
                merged_pairs.append((key, cache.get(source_value, source_value)))
            else:
                merged_pairs.append((key, target_value))
        else:
            value = cache.get(source_value, source_value) if isinstance(source_value, str) else source_value
            merged_pairs.append((key, value))

    for index, pair in enumerate(target_pairs):
        if index not in used_target_indices:
            merged_pairs.append(pair)

    return merged_pairs


def validate_file(source_path: Path, target_path: Path) -> list[str]:
    warnings: list[str] = []
    source_pairs = load_json_pairs(source_path)
    target_pairs = load_json_pairs(target_path)

    target_by_key: dict[str, list[Any]] = {}
    for key, value in target_pairs:
        target_by_key.setdefault(key, []).append(value)

    for key, source_value in source_pairs:
        target_values = target_by_key.get(key, [])
        if not target_values:
            warnings.append(f"{target_path}: {key}: missing key")
            continue
        target_value = target_values.pop(0)
        if isinstance(source_value, str) and isinstance(target_value, str):
            missing = missing_tokens(source_value, target_value)
            if missing:
                warnings.append(f"{target_path}: {key}: missing {missing!r}")

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Translate Minecraft en_us.json files to ru_ru.json in batches."
    )
    parser.add_argument("--root", default=".", help="Folder to scan recursively.")
    parser.add_argument("--source", default="en_us", help="Source lang name without .json.")
    parser.add_argument("--target", default="ru_ru", help="Target lang name without .json.")
    parser.add_argument("--from-lang", default="en", help="Translator source language.")
    parser.add_argument("--to-lang", default="ru", help="Translator target language.")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite existing target files.")
    parser.add_argument(
        "--retranslate-identical",
        action="store_true",
        dest="retranslate_identical",
        help="Retranslate keys whose target value is identical to the source (untranslated copy-paste).",
    )
    parser.add_argument("--batch-size", type=int, default=150, help="Cache save progress interval.")
    parser.add_argument("--max-chars", type=int, default=4500, help="Max chars per translator request.")
    parser.add_argument("--retries", type=int, default=3, help="Retries per failed request.")
    parser.add_argument("--retry-sleep", type=float, default=2.0, help="Base retry delay in seconds.")
    parser.add_argument(
        "--cache",
        default=".mc_lang_translation_cache_ru.json",
        help="Translation cache file path, relative to root unless absolute.",
    )
    parser.add_argument(
        "--warnings",
        default="mc_lang_translation_warnings.txt",
        help="Warnings report path, relative to root unless absolute.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    source_name = f"{args.source}.json"
    target_name = f"{args.target}.json"
    cache_path = Path(args.cache)
    warnings_path = Path(args.warnings)
    if not cache_path.is_absolute():
        cache_path = root / cache_path
    if not warnings_path.is_absolute():
        warnings_path = root / warnings_path

    files = sorted(root.rglob(source_name))
    if not files:
        print(f"No {source_name} files found under {root}")
        return 1

    if args.overwrite:
        files_to_write = files
    else:
        files_to_write = [
            path
            for path in files
            if missing_source_keys(path, path.with_name(target_name), args.retranslate_identical)
        ]

    print(f"Found source files: {len(files)}")
    print(f"Files to write/update: {len(files_to_write)}")
    if not files_to_write:
        print("Nothing to do. Targets already contain all source keys.")
        return 0

    cache = load_cache(cache_path)
    values = collect_values(files_to_write, cache, target_name, args.overwrite, args.retranslate_identical)

    print(f"Cached translations: {len(cache)}")
    print(f"New unique strings: {len(values)}")

    if values:
        translator = GoogleTranslator(source=args.from_lang, target=args.to_lang)
        for index in range(0, len(values), args.batch_size):
            batch = values[index : index + args.batch_size]
            cache.update(
                translate_many(
                    batch,
                    translator=translator,
                    max_chars=args.max_chars,
                    retries=args.retries,
                    retry_sleep=args.retry_sleep,
                )
            )
            save_cache(cache_path, cache)
            print(f"Translated {min(index + args.batch_size, len(values))}/{len(values)}")

    all_warnings: list[str] = []

    for file_index, source_path in enumerate(files_to_write, 1):
        target_path = source_path.with_name(target_name)
        target_pairs = build_target_pairs(source_path, target_path, cache, args.overwrite, args.retranslate_identical)
        target_path.write_text(dump_json_pairs(target_pairs), encoding="utf-8")
        all_warnings.extend(validate_file(source_path, target_path))
        print(f"[{file_index}/{len(files_to_write)}] wrote {target_path}")

    if all_warnings:
        warnings_path.write_text("\n".join(all_warnings) + "\n", encoding="utf-8")
        print(f"Warnings: {len(all_warnings)} -> {warnings_path}")
    elif warnings_path.exists():
        warnings_path.unlink()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
