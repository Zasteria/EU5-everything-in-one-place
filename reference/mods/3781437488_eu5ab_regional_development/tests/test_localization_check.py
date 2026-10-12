from pathlib import Path
import json
import tempfile
import unittest

from src.eu5autobuild.localization import TranslationCatalog, TranslationEntry
from src.eu5autobuild.localization_check import check_repository_localization


UTF8_BOM = b"\xef\xbb\xbf"


def _write_localization(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(UTF8_BOM + data)


class LocalizationCheckTests(unittest.TestCase):
    def _make_repository(self, root: Path) -> None:
        chinese = 'l_simp_chinese:\n sample: "标题 [Value|0]"\n'
        english = 'l_english:\n sample: "Title [Value|0]"\n'
        french = 'l_french:\n sample: "Titre [Value|0]"\n'
        for layer in ("in_game", "main_menu"):
            base = root / layer / "localization"
            _write_localization(
                base / "simp_chinese" / "eu5ab_l_simp_chinese.yml",
                chinese,
            )
            _write_localization(
                base / "english" / "eu5ab_l_english.yml",
                english,
            )
            _write_localization(base / "french" / "eu5ab_l_french.yml", french)

        catalog = TranslationCatalog(
            "french",
            {
                "sample": TranslationEntry(
                    "标题 [Value|0]",
                    "Title [Value|0]",
                    "Titre [Value|0]",
                )
            },
        )
        catalog_path = root / "localization" / "translations" / "french.json"
        catalog_path.parent.mkdir(parents=True)
        catalog_path.write_text(
            json.dumps(
                {
                    "language": catalog.language,
                    "entries": {
                        key: {
                            "source_zh": entry.source_zh,
                            "source_en": entry.source_en,
                            "translation": entry.translation,
                        }
                        for key, entry in catalog.entries.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def test_repository_check_accepts_matching_catalog_and_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            reports = check_repository_localization(root, ("french",))
            self.assertEqual(reports[0].translated, ("sample",))
            self.assertFalse(reports[0].missing)

    def test_repository_check_rejects_different_game_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            _write_localization(
                root
                / "main_menu"
                / "localization"
                / "french"
                / "eu5ab_l_french.yml",
                'l_french:\n sample: "Autre [Value|0]"\n',
            )
            with self.assertRaisesRegex(ValueError, "differs between"):
                check_repository_localization(root, ("french",))

    def test_repository_check_reports_changed_source_with_english_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repository(root)
            catalog_path = root / "localization" / "translations" / "french.json"
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            payload["entries"]["sample"]["source_en"] = "Old title [Value|0]"
            catalog_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            fallback = 'l_french:\n sample: "Title [Value|0]"\n'
            for layer in ("in_game", "main_menu"):
                _write_localization(
                    root
                    / layer
                    / "localization"
                    / "french"
                    / "eu5ab_l_french.yml",
                    fallback,
                )

            reports = check_repository_localization(root, ("french",))
            self.assertEqual(reports[0].changed, ("sample",))


if __name__ == "__main__":
    unittest.main()
