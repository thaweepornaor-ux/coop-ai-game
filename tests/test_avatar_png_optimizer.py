"""Regression tests for transparent avatar PNG optimization.

Run: python -m unittest discover -s tests -p 'test_avatar_png_optimizer.py'
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
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

    def test_prefers_high_resolution_indexed_png_over_tiny_full_color(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / "in.png", Path(d) / "out.png"
            image = Image.new("RGBA", (512, 512), (20, 80, 120, 0))
            image.putpixel((250, 250), (200, 10, 10, 255))
            image.save(source)

            def fake_encode(frame, indexed_colors=None):
                if indexed_colors is None and max(frame.size) > 160:
                    return b"x" * (module.MAX_BYTES + 1), "RGBA"
                if indexed_colors is not None:
                    return b"PNG-fast" * 20, "indexed-256"
                return b"PNG-small" * 20, "RGBA"

            with patch.object(module, "_encode", side_effect=fake_encode):
                dimensions, size, mode = module.optimize(source, target)
            self.assertEqual(dimensions, (512, 512))
            self.assertEqual(mode, "indexed-256")
            self.assertLessEqual(size, module.MAX_BYTES)

    def test_real_image_optimization_preserves_partial_alpha_and_file_budget(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / "input.png", Path(d) / "result.png"
            im = Image.new("RGBA", (512, 512), (80, 140, 210, 0))
            for y in range(80, 430):
                for x in range(80, 430):
                    alpha = max(0, min(255, (x - 80) * 255 // 350))
                    im.putpixel((x, y), ((x * 31) % 256, (y * 17) % 256, 120, alpha))
            im.save(source)
            dimensions, byte_count, _ = module.optimize(source, target)
            self.assertLessEqual(byte_count, module.MAX_BYTES)
            self.assertLessEqual(max(dimensions), module.MAX_DIMENSION)
            with Image.open(target) as result:
                self.assertEqual(result.format, "PNG")
                alpha = result.convert("RGBA").getchannel("A")
                self.assertEqual(alpha.getextrema()[0], 0)
                self.assertGreater(alpha.getextrema()[1], 0)

    def test_real_image_retains_sem_transparency_and_png_signature(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / "source.png", Path(d) / "avatar.png"
            image = Image.new("RGBA", (512, 640), (0, 0, 0, 0))
            for y in range(90, 550):
                for x in range(110, 400):
                    alpha = 255 if 120 < x < 390 else 100
                    image.putpixel((x, y), ((x * 7) % 255, (y * 3) % 255, 155, alpha))
            image.save(source)
            dims, count, mode = module.optimize(source, target)
            self.assertLessEqual(count, 150 * 1024)
            self.assertTrue(target.read_bytes().startswith(bytes((137, 80, 78, 71, 13, 10, 26, 10))))
            with Image.open(target) as output:
                self.assertEqual(output.size, dims)
                alpha = output.convert("RGBA").getchannel("A")
                self.assertEqual(alpha.getextrema(), (0, 255))
            self.assertTrue(mode == "RGBA" or mode.startswith("indexed-"))

    def test_rejects_non_png_and_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / "image.jpg", Path(d) / "result.png"
            Image.new("RGB", (96, 96), (20, 30, 40)).save(source)
            target.write_bytes(b"keep-me")
            with self.assertRaises(ValueError):
                module.optimize(source, target)
            self.assertEqual(target.read_bytes(), b"keep-me")

if __name__ == "__main__":
    unittest.main()
