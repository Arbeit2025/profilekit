import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as profilekit

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
NAME_RE = re.compile(r"^[a-z0-9_.]+$")


class PageTest(unittest.TestCase):
    def setUp(self):
        self.client = profilekit.app.test_client()

    def test_index_ok(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("profilekit", body)
        self.assertIn('name="theme"', body)
        self.assertIn('name="keyword"', body)
        self.assertIn('name="style"', body)
        self.assertIn('name="use_numbers"', body)

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"status": "ok"})

    def test_generate_post_shows_six_kits(self):
        res = self.client.post("/generate", data={
            "theme": "cute", "keyword": "", "style": "identicon",
            "use_numbers": "1",
        })
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertEqual(body.count("/icon?name="), 6)

    def test_generate_escapes_keyword(self):
        res = self.client.post("/generate", data={
            "theme": "cute", "keyword": "<script>", "style": "identicon",
        })
        body = res.get_data(as_text=True)
        self.assertNotIn("<script>", body)


class NameGenerationTest(unittest.TestCase):
    def test_count_and_charset(self):
        names = profilekit.generate_names(theme="cute", count=6, seed=42)
        self.assertEqual(len(names), 6)
        self.assertEqual(len(set(names)), 6)
        for name in names:
            self.assertRegex(name, NAME_RE)

    def test_keyword_reflected_in_all_candidates(self):
        names = profilekit.generate_names(theme="random", keyword="cocoa",
                                          count=6, seed=7)
        self.assertEqual(len(names), 6)
        for name in names:
            self.assertIn("cocoa", name)

    def test_no_numbers_when_disabled(self):
        names = profilekit.generate_names(theme="space", count=10,
                                          use_numbers=False, seed=3)
        for name in names:
            self.assertFalse(any(c.isdigit() for c in name))

    def test_unknown_theme_raises(self):
        with self.assertRaises(ValueError):
            profilekit.generate_names(theme="nope")

    def test_sanitize_keyword(self):
        self.assertEqual(profilekit.sanitize_keyword("  CoCoA!! "), "cocoa")
        self.assertEqual(profilekit.sanitize_keyword("a b_c.d"), "ab_c.d")
        self.assertEqual(profilekit.sanitize_keyword(""), "")
        self.assertEqual(profilekit.sanitize_keyword("..x.."), "x")


class BioTest(unittest.TestCase):
    def test_bio_contains_name_for_every_theme(self):
        for theme in profilekit.THEME_LABELS:
            bio = profilekit.make_bio("test_name", theme)
            self.assertIn("test_name", bio)

    def test_bio_templates_at_least_three_per_theme(self):
        for theme, templates in profilekit.BIO_TEMPLATES.items():
            self.assertGreaterEqual(len(templates), 3, theme)


class IconTest(unittest.TestCase):
    def setUp(self):
        self.client = profilekit.app.test_client()

    def test_all_styles_return_png(self):
        for style in ("identicon", "geometric", "pixel"):
            res = self.client.get(f"/icon?name=cocoa&style={style}")
            self.assertEqual(res.status_code, 200, style)
            self.assertEqual(res.mimetype, "image/png")
            self.assertTrue(res.data.startswith(PNG_MAGIC), style)

    def test_deterministic_same_name_same_bytes(self):
        for style in ("identicon", "geometric", "pixel"):
            first = self.client.get(f"/icon?name=mochi&style={style}").data
            second = self.client.get(f"/icon?name=mochi&style={style}").data
            self.assertEqual(first, second, style)

    def test_different_names_different_bytes(self):
        a = self.client.get("/icon?name=alpha&style=identicon").data
        b = self.client.get("/icon?name=omega&style=identicon").data
        self.assertNotEqual(a, b)

    def test_generate_icon_function_deterministic(self):
        self.assertEqual(profilekit.generate_icon("sakura", "pixel"),
                         profilekit.generate_icon("sakura", "pixel"))

    def test_icon_missing_name_400(self):
        res = self.client.get("/icon?style=identicon")
        self.assertEqual(res.status_code, 400)

    def test_icon_unknown_style_400(self):
        res = self.client.get("/icon?name=cocoa&style=nope")
        self.assertEqual(res.status_code, 400)


class KitTest(unittest.TestCase):
    def test_build_kit_has_six_entries_with_bio(self):
        kits = profilekit.build_kit(theme="food", style="pixel", seed=11)
        self.assertEqual(len(kits), 6)
        for kit in kits:
            self.assertRegex(kit["name"], NAME_RE)
            self.assertEqual(kit["style"], "pixel")
            self.assertIn(kit["name"], kit["bio"])


if __name__ == "__main__":
    unittest.main()
