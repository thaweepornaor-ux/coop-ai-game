# Audit of original CGI avatar PNG candidates (2026-10-12)

Source inspected: original local candidate archive `coop_avatar_integration_candidate_20261012.zip`, not the tiny thumbnails already committed to `public/avatar-parts/`. No new art has been approved or published.

| Original PNG | Native size | QA verdict |
| --- | ---: | --- |
| `assets/male.png` | 1306 x 1205 | Good-quality separate CGI face, no full body |
| `assets/female.png` | 1306 x 1205 | Good-quality separate CGI face, no full body |
| `assets/hair2.png` | 1024 x 1536 | Hair-only cutout, requires alignment |
| `assets/hair4.png` | 1306 x 1205 | Hair-only cutout, requires alignment |
| `assets/clothing_male_beige_overshirt.png` | 154 x 148 | Small clothing cutout; insufficient resolution for close-up full-body game rendering |
| `assets/clothing_male_beige_chinos.png` | 154 x 147 | **Visually depicts shorts**; catalog's `pants` mapping is not accurate as a long-pants replacement |
| `assets/shoes_female_white_sneakers.png` | 154 x 148 | Small footwear cutout; proportion and gender suitability require separate review |

Do not mark these parts `aligned:true` simply because they are available. Authentic transparent **full-body male and female bases are still missing**.

## Measured encoding candidates under 150 KiB (experiment only, not imported)

Values were computed against original PNG images at the given resolution using Pillow `quantize(FASTOCTREE)`, PNG optimize and compression level 9:

| Image | Candidate dimensions | Encoding | Encoded bytes |
| --- | --- | --- | ---: |
| `male.png` | 1024 x 945 | 256-color indexed PNG | 149624 |
| `female.png` | 1024 x 945 | 192-color indexed PNG | 153328 |
| `hair2.png` | 512 x 768 | 256-color indexed PNG | 96250 |
| `hair4.png` | 768 x 709 | 256-color indexed PNG | 105958 |

Those candidates require visual approval before any upload. Prioritize quality and proportion, not simply a smaller file. Existing public thumbnails are much smaller and should not be upscaled.
