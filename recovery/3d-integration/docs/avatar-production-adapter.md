# Genuine GLB adapter staging proposal

Base source: `18ac3864c1776346bbfab28750789bdeefea1548`.
This proposal does not publish, change a Git ref, replace the game backend, or certify new art.

## Current activation

`shared/avatar-production-assets.ts` deliberately exports
`PRODUCTION_AVATAR_ENABLED = false` and a null manifest.
The public `Avatar` continues to render the exact existing implementation.
The optional `animation` prop is additive; existing calls and stored avatar selections work unchanged.

When the flag is eventually enabled, the production adapter fails visibly if assets are
unavailable. It does not display legacy art while labelling it genuine GLB art.
A device without WebGL2 can continue playing; an already available matching thumbnail
is shown, otherwise a brief unavailable message is shown.

## Dependency delta

Add only this exact runtime dependency to the current package and regenerate the lockfile in CI:

```json
{ "dependencies": { "three": "0.180.0" } }
```

The runtime is JavaScript ESM with a typed public `.d.mts` boundary. No `@types/three`,
extra decoder package, optimizer or asset-download dependency is required by this proposal.
Do not replace a newer package.json with the proposal's full snapshot without reconciling
other changes. Preserve the current pnpm override/workspace and Cloudflare configuration.

## Asset contract

The manifest contains two body entries, `male` and `female`, each with:

- An approved same-origin `/avatars/production/...glb` URL, exact SHA-256 and byte length,
  uniquely named rig root, scale and yaw.
- A fixed studio camera; changing asset/camera/binding data invalidates cached previews.
- The exact ten canonical preset IDs for that gender.
- Four geometry-choice bindings: hairStyle, shirtStyle, bottomStyle, hatStyle.
- Six independent color bindings: skinTone, hairColor, shirtColor, bottomColor, shoeColor, hatColor.
  bodyStyle is the two-body asset selection, bringing the original wardrobe fields to eleven.
- The three actual exported clip names mapped to idle, wave and celebrate.
- Accepted export validation plus separate art and browser review references.

Each geometry state has the form:

```ts
{
  visibility: Record<actualMeshName, boolean>,
  morphs: [{ mesh: actualMeshName, target: actualMorphName, value: finiteWeight }]
}
```

Every option in a field must completely assign the same owned visibility/morph targets.
The runtime applies complete states, so selecting "none"/"bald" or switching back from
a garment cannot retain hidden state from the previous choice.
A clothing state may include authored torso/leg coverage meshes or corrective morphs.
Those must have separate ownership between fields; do not let a shirt and a skirt
fight over one body mask. No scaling of bones or guessed mesh names is used.

A color binding has `kind: 'color'`, uniquely named independent PBR material targets,
and a choices table matching every exact canonical palette value. Materials are cloned
per avatar while retaining sharing between slots inside that avatar. Base textures remain
intact. Artists must author recolorable material/texture regions; the runtime cannot
prove that multiplying a textured region gives the intended skin/fabric appearance.

The current whitelist has 13 hair styles, 4 shirt styles, 2 bottom styles and 4 hat choices
including none. Both bodies must cover all of them. Changing the whitelist is outside this proposal.
The twenty identity states must be different authored geometry states, with actual
nonzero head/face morphs or distinct head/accessory meshes. Different labels, IDs or colors
on one unchanged head do not satisfy this contract. The scalar design values in
characters.ts do not prove matching GLB morphs exist.

## Runtime ownership and checks

Before creating any avatar, both body GLBs are loaded and validated. The reader verifies
the header/chunks, reviewed SHA/byte count, self-contained resources, no extra JOINTS_1/
WEIGHTS_1 and no required extensions requiring an unconfigured decoder. The loaded
scene must resolve all names unambiguously, contain a deforming skeleton under the
declared root, four finite normalized influences, actual geometry-changing morphs,
independent PBR color materials and three clips with changing local joint tracks.
Common rig-root/global motion and quaternion sign/length-only changes do not count.

This reader complements the production GLB validator and art review. It is not a full
glTF validator, influence-loss comparison, pose/render validation or proof that all
faces are visually distinguishable. Source skeleton materials/clothing still need actual
Rain/Snow inventory/export work; no production target names are invented here.

The immutable master scene is cloned with SkeletonUtils. Each instance owns its bones,
skeleton resources, cloned materials and AnimationMixer. Geometry/textures remain owned
by the shared master catalogue until no instance/request owns them. Appearance morphs
are restored after mixer updates so a full-head animation weight channel cannot reset
the selected identity. Animation never substitutes root bobbing for a missing clip.

Exactly one interactive hero is allowed. Its existing canvas is reused for same-rig
wardrobe changes. A new rig key gets a new canvas. Disposal does not force context loss
on a still-connected canvas, allowing React cleanup/reuse; detached canvases are released.
The RAF stops when hidden, outside view, motion-disabled or reduced-motion is enabled.
The OS preference is subscribed live. Resume resets timing and caps frame delta.
Context loss stops rendering and retains matching preview state; restoration rebuilds
Three GPU state and redraws. Loading/abort generations cannot install stale choices.

Noninteractive avatars use images. Thumbnail generation has one serialized renderer,
in-flight deduplication and cancellable queued waiters. Therefore the adapter has at most
one hero plus one temporary thumbnail WebGL context, never a canvas for every preset or row.
The auxiliary renderer is retired after 30 seconds idle.
The LRU retains up to 64 previews / 16 MiB of compressed PNG data when entries are unleased.
Visible image leases are not revoked; pinned entries can temporarily exceed these cache
targets. The budget is not a guarantee for total decoded image/GPU memory.
Keys include the render revision, asset hash/camera/bindings and all normalized 12 selections.
A released lease permits eviction; unmount/abort returns ownership.

## Collecting evidence before activation

The runtime factories accept an explicit `mode: 'staging'`. It still requires complete
manifest coverage and accepted export-validation evidence, but permits pending art/browser
review fields. Use it in a local CI preview harness to obtain real browser evidence before
approving those fields. The public Avatar component never supplies staging mode.
A staging load is not production acceptance, and it does not activate the game renderer.

Examples of the API, using a real complete manifest:

```js
const warm = await prepareProductionCatalog(manifest, { mode: 'staging' });
try {
  const controller = await createProductionHero(canvas, canonicalSelections, {
    manifest, mode: 'staging', signal, motion: true, visible: true,
  });
  // controller.play('wave'); controller.updateSelection(nextCanonicalSelections);
  // controller.dispose() owns renderer/mixer/material release.
} finally { warm.release(); }
```

The static image API returns a lease:
`await acquireProductionThumbnail(selection, { manifest, signal, mode: 'staging' })`.
Release it after the image is no longer shown. For an idle process with no active jobs,
`disposeUnusedProductionResources()` clears only unowned masters/unleased previews.
Do not invoke this administrative helper during a thumbnail job.

## Verification required

Run contract tests with the actual installed Node:
`node --experimental-strip-types --test tests/avatar-production-contract.test.mjs`.
The fixtures are synthetic schema examples, not fabricated production assets.

Then run the real build against the regenerated lockfile and a local preview.
Use actual exported GLBs to check every preset and all 11 fields; compare independent
instances for material/morph leakage. Test fast preset changes, same-rig edits, body swaps,
refresh, hidden/resume, live reduced-motion, pointer/keyboard rotation, forced context
loss/restoration and WebGL2 unavailable. Validate actual idle/wave/celebrate motion, hands,
face, neck/shoulder/hem coverage in neutral and raised-arm poses, and mobile camera framing.
Existing browser proof of the old renderer does not certify this adapter.

Primary pinned implementation references:

- https://raw.githubusercontent.com/mrdoob/three.js/r180/package.json
- https://raw.githubusercontent.com/mrdoob/three.js/r180/examples/jsm/loaders/GLTFLoader.js
- https://raw.githubusercontent.com/mrdoob/three.js/r180/examples/jsm/utils/SkeletonUtils.js
- https://raw.githubusercontent.com/mrdoob/three.js/r180/src/renderers/WebGLRenderer.js
- https://raw.githubusercontent.com/mrdoob/three.js/r180/src/animation/AnimationMixer.js
