import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
FENLIGHT_ROOT = REPO_ROOT / "plugin.video.fenlight.patched"
COCOSCRAPERS_ROOT = REPO_ROOT / "script.module.cocoscrapers"


class ExternalScraperDefaultsTests(unittest.TestCase):
    def test_cocoscrapers_is_the_required_default_scraper(self):
        root = ET.parse(FENLIGHT_ROOT / "addon.xml").getroot()
        required = {
            item.attrib["addon"]: item.attrib.get("version")
            for item in root.findall("./requires/import")
        }
        self.assertEqual(required["script.module.cocoscrapers"], "1.0.43")
        self.assertNotIn("script.module.magneto", required)

    def test_settings_default_to_cocoscrapers(self):
        settings_source = (FENLIGHT_ROOT / "resources/lib/caches/settings_cache.py").read_text()
        self.assertIn("'external_scraper.name', 'setting_type': 'string', 'setting_default': 'CocoScrapers Module'", settings_source)
        self.assertIn("'external_scraper.module', 'setting_type': 'string', 'setting_default': 'script.module.cocoscrapers'", settings_source)

    def test_update_migrates_magneto_selection_to_cocoscrapers(self):
        tree = ast.parse((FENLIGHT_ROOT / "resources/lib/service.py").read_text())
        migration = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "migrate_external_scraper_to_cocoscrapers"
        )
        source = ast.unparse(migration)
        self.assertIn("current_module != 'script.module.magneto'", source)
        self.assertIn("script.module.cocoscrapers", source)
        self.assertIn("CocoScrapers Module", source)

    def test_cocoscrapers_retains_fenlight_legacy_interface(self):
        scraper_source = (COCOSCRAPERS_ROOT / "lib/cocoscrapers/__init__.py").read_text()
        control_source = (COCOSCRAPERS_ROOT / "lib/cocoscrapers/modules/control.py").read_text()
        self.assertIn("def sources(", scraper_source)
        self.assertIn("def getProviderDefaults(", control_source)


if __name__ == "__main__":
    unittest.main()
