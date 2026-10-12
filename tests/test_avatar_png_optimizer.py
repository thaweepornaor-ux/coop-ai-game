"""Regression tests for transparent avatar PNG optimization.

Run: python -m unittest discover -s tests -p 'test_avatar_png_optimizer.py'
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "optimize-avatar-png.py"
spec = importlib.util.spec_from_file_location("avatar_png_optimizer", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AvatarPngOptimizerTests(unittest.TestCase):
    def test_small_alpha_image_remains_transparent_and_is_not_upscaled(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / "in.png", Path(d) / "out.png"
            Image.new("RGBA", (80, 96), (25, 85, 200, 0)).save(source)
            dims, count, mode = module.optimize(source, target)
            self.assertEqual(dims, (80, 96))
            self.assertLessEqual(count, 150 * 1024)
            with Image.open(target) as result:
                self.assertEqual(result.size, (80, 96))
                self.assertLess(result.convert("RGBA").getchannel("A").getextrema()[0], 255)
            self.assertEqual(mode, "RGBA")

    def test_rejects_opaque_png_without_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / "opaque.png", Path(d) / "out.png"
            Image.new("RGB", (100, 100), (0, 0, 0)).save(source)
            with self.assertRaises(ValueError):
                module.optimize(source, target)
            self.assertFalse(target.exists())

    def test_rejects_invalid_limit_and_does_not_overwrite_source(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "in.png"
            Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(source)
            original = source.read_bytes()
            with self.assertRaises(ValueError):
                module.optimize(source, source)
            with self.assertRaises(ValueError):
                module.optimize(source, Path(d) / "out.png", 150 * 1024 + 1)
            self.assertEqual(source.read_bytes(), original)

if __name__ == "__main__":
    unittest.main()
