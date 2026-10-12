"""Validate checked-in translation catalogs and generated localization files."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .localization import (
    SUPPORTED_TRANSLATION_LANGUAGES,
    LocalizationReport,
    load_translation_catalog,
    render_translated_localization,
    translation_report,
)


ROOT = Path(__file__).resolve().parents[2]


def _read_generated_localization(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    if not data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"Localization file must use a UTF-8 BOM: {path}")
    body = data[3:]
    if b"\n" in body.replace(b"\r\n", b"") or b"\r" in body.replace(
        b"\r\n", b""
    ):
        raise ValueError(f"Localization file must use CRLF line endings: {path}")
    if not data.endswith(b"\r\n"):
        raise ValueError(f"Localization file must end with CRLF: {path}")
    return data, data.decode("utf-8-sig").replace("\r\n", "\n")


def _validate_catalog_line_endings(path: Path) -> None:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"Translation catalog must use UTF-8 without BOM: {path}")
    if b"\r" in data:
        raise ValueError(f"Translation catalog must use LF line endings: {path}")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Translation catalog is not valid UTF-8: {path}") from error


def _layer_paths(root: Path, language: str) -> tuple[Path, Path]:
    filename = f"eu5ab_l_{language}.yml"
    return (
        root / "in_game" / "localization" / language / filename,
        root / "main_menu" / "localization" / language / filename,
    )


def check_repository_localization(
    root: Path = ROOT,
    languages: tuple[str, ...] = SUPPORTED_TRANSLATION_LANGUAGES,
) -> tuple[LocalizationReport, ...]:
    """Validate catalogs, source state, markup, encoding, and generated layers."""
    chinese_paths = _layer_paths(root, "simp_chinese")
    english_paths = _layer_paths(root, "english")
    chinese_bytes, chinese = _read_generated_localization(chinese_paths[0])
    english_bytes, english = _read_generated_localization(english_paths[0])
    if chinese_bytes != _read_generated_localization(chinese_paths[1])[0]:
        raise ValueError("Simplified Chinese localization differs between game layers")
    if english_bytes != _read_generated_localization(english_paths[1])[0]:
        raise ValueError("English localization differs between game layers")

    reports: list[LocalizationReport] = []
    translation_root = root / "localization" / "translations"
    expected_catalogs = {f"{language}.json" for language in languages}
    unexpected_catalogs = sorted(
        path.name
        for path in translation_root.glob("*.json")
        if path.name not in expected_catalogs
    )
    if unexpected_catalogs:
        raise ValueError(
            "Unexpected translation catalogs: " + ", ".join(unexpected_catalogs)
        )
    for language in languages:
        catalog_path = translation_root / f"{language}.json"
        _validate_catalog_line_endings(catalog_path)
        catalog = load_translation_catalog(catalog_path, language)
        report = translation_report(chinese, english, catalog)
        expected = render_translated_localization(chinese, english, catalog)

        in_game_path, main_menu_path = _layer_paths(root, language)
        in_game_bytes, in_game = _read_generated_localization(in_game_path)
        main_menu_bytes, _ = _read_generated_localization(main_menu_path)
        if in_game_bytes != main_menu_bytes:
            raise ValueError(
                f"{language} localization differs between in_game and main_menu"
            )
        if in_game != expected:
            raise ValueError(
                f"Generated {language} localization is out of date; run the generator"
            )
        reports.append(report)
    return tuple(reports)


def _print_report(report: LocalizationReport) -> None:
    print(
        f"{report.language}: translated={len(report.translated)} "
        f"missing={len(report.missing)} changed={len(report.changed)} "
        f"obsolete={len(report.obsolete)}"
    )
    catalog_path = Path("localization") / "translations" / f"{report.language}.json"
    for label, keys in (
        ("missing", report.missing),
        ("changed", report.changed),
        ("obsolete", report.obsolete),
    ):
        if not keys:
            continue
        print(f"  {label}: {', '.join(keys)}")
        if "GITHUB_ACTIONS" in os.environ:
            print(
                f"::warning file={catalog_path.as_posix()}::"
                f"{report.language} {label}: {', '.join(keys)}"
            )


def main() -> None:
    try:
        reports = check_repository_localization()
    except (OSError, ValueError) as error:
        print(f"Localization validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    for report in reports:
        _print_report(report)


if __name__ == "__main__":
    main()
