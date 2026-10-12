# Avatar PNG production checklist

Game loading budgets are enforced by `tests/avatar-binary-assets.test.mjs`:
- Maximum **150 KiB per committed ready PNG**.
- Maximum **1 MiB combined** for PNGs marked ready in the catalog.
- Maximum 1024 px for each dimension.

Prepare assets from the full-quality source PNG (never upscale the existing tiny thumbnails):

```bash
python -m pip install Pillow
python scripts/optimize-avatar-png.py ./source/male.png ./public/avatar-parts/male.png
npm test
```

The optimizer resizes with Lanczos, tries lossless RGBA first, and uses a smaller indexed-color PNG with transparency only when necessary to meet the budget. Inspect sharpness, edge halos and clothing details before replacing an approved part. Keep a backup of originals outside the published `public/` folder, do not add the original megabyte images to the game repository. Replacing a ready asset still requires full body/alignment review; small filesize alone is **not** approval to enable PNG Avatar mode.

Note: JPEG does not retain alpha transparency; WebP/AVIF can be considered later after verifying browser/runtime support and adjusting the catalog/tests accordingly.
