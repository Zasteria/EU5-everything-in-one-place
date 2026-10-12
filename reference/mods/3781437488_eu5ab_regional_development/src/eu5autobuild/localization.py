"""Load reviewed translations and render explicit English fallbacks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .ui_values import bind_ui_values


LOCALIZATION_LINE = re.compile(r'^ ([A-Za-z0-9_.]+): ("(?:[^"\\]|\\.)*")$')
MARKUP_TOKEN = re.compile(
    r"\$[^$]+\$|\[[^\[\]]+\]|@[A-Za-z0-9_]+!|#[A-Za-z0-9_]+|#!"
)
SUPPORTED_TRANSLATION_LANGUAGES = (
    "braz_por",
    "french",
    "german",
    "japanese",
    "korean",
    "polish",
    "russian",
    "spanish",
    "turkish",
)


@dataclass(frozen=True)
class TranslationEntry:
    source_zh: str
    source_en: str
    translation: str


@dataclass(frozen=True)
class TranslationCatalog:
    language: str
    entries: dict[str, TranslationEntry]


@dataclass(frozen=True)
class LocalizationReport:
    language: str
    translated: tuple[str, ...]
    missing: tuple[str, ...]
    changed: tuple[str, ...]
    obsolete: tuple[str, ...]


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_localization(localization: str, expected_language: str) -> dict[str, str]:
    """Parse the small EU5 YAML subset emitted by this project."""
    lines = localization.splitlines()
    expected_header = f"l_{expected_language}:"
    if not lines or lines[0] != expected_header:
        raise ValueError(
            f"Localization header must be {expected_header!r}, got "
            f"{lines[0] if lines else '<empty>'!r}"
        )

    values: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:], start=2):
        if not line:
            continue
        match = LOCALIZATION_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"Invalid localization line {line_number}: {line!r}")
        key, quoted_value = match.groups()
        if key in values:
            raise ValueError(f"Duplicate localization key: {key}")
        values[key] = json.loads(quoted_value)
    return values


def load_translation_catalog(path: Path, expected_language: str) -> TranslationCatalog:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Missing translation catalog: {path}") from error

    if not isinstance(payload, dict):
        raise ValueError(f"Translation catalog must contain an object: {path}")
    if payload.get("language") != expected_language:
        raise ValueError(
            f"Translation catalog {path} declares {payload.get('language')!r}; "
            f"expected {expected_language!r}"
        )
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, dict):
        raise ValueError(f"Translation catalog entries must be an object: {path}")

    entries: dict[str, TranslationEntry] = {}
    for key, raw_entry in raw_entries.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.]+", key):
            raise ValueError(f"Invalid translation key in {path}: {key!r}")
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Translation entry {key} in {path} must be an object")
        if set(raw_entry) != {"source_zh", "source_en", "translation"}:
            raise ValueError(
                f"Translation entry {key} in {path} must contain exactly "
                "source_zh, source_en, and translation"
            )
        if not all(isinstance(raw_entry[field], str) for field in raw_entry):
            raise ValueError(f"Translation entry {key} in {path} must contain strings")
        if not raw_entry["translation"] and raw_entry["source_en"]:
            raise ValueError(f"Translation entry {key} in {path} is empty")
        entries[key] = TranslationEntry(
            source_zh=raw_entry["source_zh"],
            source_en=raw_entry["source_en"],
            translation=raw_entry["translation"],
        )
    return TranslationCatalog(language=expected_language, entries=entries)


def _markup_signature(value: str) -> Counter[str]:
    return Counter(MARKUP_TOKEN.findall(value))


def _validate_translation_markup(key: str, source_en: str, translation: str) -> None:
    if _markup_signature(source_en) != _markup_signature(translation):
        raise ValueError(f"Translation changes EU5 markup tokens for {key}")
    if source_en.count("\n") != translation.count("\n"):
        raise ValueError(f"Translation changes newline count for {key}")


def translation_report(
    chinese_localization: str,
    english_localization: str,
    catalog: TranslationCatalog,
) -> LocalizationReport:
    # Compare the same engine bindings before and after generated-file output.
    chinese = parse_localization(bind_ui_values(chinese_localization), "simp_chinese")
    english = parse_localization(bind_ui_values(english_localization), "english")
    if tuple(chinese) != tuple(english):
        raise ValueError("Chinese and English localization keys or ordering differ")

    translated: list[str] = []
    missing: list[str] = []
    changed: list[str] = []
    for key, english_value in english.items():
        entry = catalog.entries.get(key)
        if entry is None:
            missing.append(key)
        elif (
            bind_ui_values(entry.source_zh) != chinese[key]
            or bind_ui_values(entry.source_en) != english_value
        ):
            changed.append(key)
        else:
            _validate_translation_markup(key, english_value, bind_ui_values(entry.translation))
            translated.append(key)
    obsolete = [key for key in catalog.entries if key not in english]
    return LocalizationReport(
        language=catalog.language,
        translated=tuple(translated),
        missing=tuple(missing),
        changed=tuple(changed),
        obsolete=tuple(obsolete),
    )


def render_translated_localization(
    chinese_localization: str,
    english_localization: str,
    catalog: TranslationCatalog,
) -> str:
    english = parse_localization(english_localization, "english")
    report = translation_report(chinese_localization, english_localization, catalog)
    usable = set(report.translated)

    lines = [f"l_{catalog.language}:"]
    for key, english_value in english.items():
        value = catalog.entries[key].translation if key in usable else english_value
        lines.append(f" {key}: {json.dumps(bind_ui_values(value), ensure_ascii=False)}")
    return "\n".join(lines) + "\n"
