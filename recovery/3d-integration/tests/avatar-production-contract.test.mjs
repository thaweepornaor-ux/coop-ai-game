import assert from 'node:assert/strict';
import test from 'node:test';
import { AVATAR_OPTIONS } from '../shared/avatar.js';
import { CHARACTERS } from '../shared/characters.ts';
import { GEOMETRY_FIELDS, COLOR_FIELDS, validateProductionManifest, assertProductionManifest,
  AssetCapabilityError, thumbnailKey } from '../shared/avatar-production-contract.mjs';

/** Schema fixtures only: these names and hashes are synthetic and are never production assets. */
function fixture() {
  const bodies = {};
  for (const gender of ['male', 'female']) {
    const wardrobe = {};
    for (const field of GEOMETRY_FIELDS) {
      const nodes = AVATAR_OPTIONS[field].filter(o => o.value !== 'none' && o.value !== 'bald').map(o => field + ':' + o.value);
      wardrobe[field] = { kind: 'geometry', choices: Object.fromEntries(AVATAR_OPTIONS[field].map(option =>
        [option.value, { visibility: Object.fromEntries(nodes.map(node => [node, node === field + ':' + option.value])), morphs: [] }])) };
    }
    for (const field of COLOR_FIELDS) wardrobe[field] = {
      kind: 'color', materials: [field + ':material'],
      choices: Object.fromEntries(AVATAR_OPTIONS[field].map(option => [option.value, option.color])),
    };
    const presets = Object.fromEntries(CHARACTERS.filter(p => p.gender === gender).map((preset, index) =>
      [preset.id, { visibility: { Glasses: preset.glasses },
        morphs: [{ mesh: 'Head', target: 'FaceWidth', value: (index + 1) / 10 }] }]));
    bodies[gender] = {
      asset: { url: '/avatars/production/test/' + gender + '.glb', sha256: '1'.repeat(64), byteLength: 200,
        rigRoot: 'Armature', scale: 1, rotationY: 0 },
      camera: { position: [0, 1, 4], target: [0, 1, 0], fov: 35, near: .1, far: 100 },
      presets, wardrobe, clips: { idle: 'Idle', wave: 'Wave', celebrate: 'Celebrate' },
    };
  }
  return { schemaVersion: 1, revision: 'synthetic-test', threeVersion: '0.180.0',
    evidence: Object.fromEntries(['exportValidation', 'artReview', 'browserReview']
      .map(name => [name, { accepted: true, reference: 'Synthetic contract fixture, not rendered evidence' }])),
    bodies };
}
const copy = value => JSON.parse(JSON.stringify(value));
const invalid = (manifest, pattern) => {
  const result = validateProductionManifest(manifest);
  assert.equal(result.ready, false);
  assert.ok(result.issues.some(issue => pattern.test(issue)), result.issues.join('; '));
};

test('complete synthetic coverage is valid schema, without asserting asset/render validity', () => {
  assert.equal(validateProductionManifest(fixture()).ready, true);
});
test('null manifest keeps production unavailable', () => invalid(null, /absent/));
test('both genders and exactly twenty canonical identities are required', () => {
  const missingBody = fixture(); delete missingBody.bodies.female; invalid(missingBody, /female/);
  const missingIdentity = fixture(); delete missingIdentity.bodies.male.presets.M10; invalid(missingIdentity, /identity IDs/);
  const wrongGender = fixture(); wrongGender.bodies.male.presets.F01 = wrongGender.bodies.male.presets.M01; invalid(wrongGender, /identity IDs/);
});
test('all thirteen hair enum values and every other wardrobe enum must survive', () => {
  for (const field of [...GEOMETRY_FIELDS, ...COLOR_FIELDS]) {
    const manifest = fixture(); delete manifest.bodies.female.wardrobe[field].choices[AVATAR_OPTIONS[field][0].value];
    invalid(manifest, /incomplete enum coverage/);
  }
  assert.equal(AVATAR_OPTIONS.hairStyle.length, 13);
});
test('identity differences cannot be labels, metadata or reordered identical morphs', () => {
  const manifest = fixture();
  const first = copy(manifest.bodies.male.presets.M01);
  manifest.bodies.male.presets.M02 = { ...first, label: 'Different label' };
  invalid(manifest, /duplicate identity geometry/);
});
test('geometry styles cannot alias the same authored state', () => {
  const manifest = fixture();
  manifest.bodies.male.wardrobe.shirtStyle.choices.polo = copy(manifest.bodies.male.wardrobe.shirtStyle.choices.tshirt);
  invalid(manifest, /duplicate geometry choice/);
});
test('each geometry option completely assigns its owned targets', () => {
  const manifest = fixture();
  delete manifest.bodies.female.wardrobe.hatStyle.choices.none.visibility['hatStyle:cap'];
  invalid(manifest, /target coverage differs/);
});
test('wardrobe fields and identity cannot overwrite another field target', () => {
  const material = fixture(); material.bodies.male.wardrobe.hairColor.materials = ['skinTone:material']; invalid(material, /is shared/);
  const mesh = fixture();
  for (const state of Object.values(mesh.bodies.male.wardrobe.hairStyle.choices)) state.visibility.Glasses = false;
  invalid(mesh, /shared by identity and hairStyle/);
});
test('the exact canonical palettes are required', () => {
  const manifest = fixture(); manifest.bodies.male.wardrobe.shirtColor.choices.red = '#000000';
  invalid(manifest, /canonical palette/);
});
test('review references and exact renderer version are required', () => {
  const manifest = fixture(); manifest.evidence.browserReview.accepted = false; invalid(manifest, /browserReview/);
  const version = fixture(); version.threeVersion = '0.181.0'; invalid(version, /renderer version/);
});
test('approved same-origin URL, reviewed SHA and byte length are required', () => {
  for (const url of ['https://elsewhere.test/avatar.glb', '/avatars/production/../other.glb', '/avatars/production//a.glb']) {
    const manifest = fixture(); manifest.bodies.male.asset.url = url; invalid(manifest, /asset URL/);
  }
  const hash = fixture(); hash.bodies.male.asset.sha256 = ''; invalid(hash, /SHA-256/);
  const size = fixture(); size.bodies.male.asset.byteLength = 40000000; invalid(size, /byte limit/);
});
test('idle, wave and celebrate must map to separate exported clips', () => {
  const manifest = fixture(); manifest.bodies.female.clips.wave = 'Idle'; invalid(manifest, /distinct exported clips/);
});
test('malformed nested data fails as a result rather than throwing', () => {
  const manifest = fixture();
  manifest.bodies.male.presets.M01.morphs = [null];
  manifest.bodies.female.wardrobe.hairColor.materials = {};
  manifest.bodies.female.wardrobe.skinTone.choices.fair = { toLowerCase: 12 };
  assert.doesNotThrow(() => validateProductionManifest(manifest));
  assert.equal(validateProductionManifest(manifest).ready, false);
});
test('non-finite camera and morph data are rejected', () => {
  const camera = fixture(); camera.bodies.male.camera.far = Infinity; invalid(camera, /studio camera/);
  const morph = fixture(); morph.bodies.male.presets.M01.morphs[0].value = NaN; invalid(morph, /invalid morph/);
});
test('assertion throws a typed readiness error', () => {
  assert.throws(() => assertProductionManifest(null), AssetCapabilityError);
});
test('cache keys include revision, every wardrobe field and preset identity', () => {
  const manifest = fixture();
  const selection = Object.fromEntries(Object.entries(AVATAR_OPTIONS).map(([key, options]) => [key, options[0].value]));
  selection.presetId = 'M01';
  const key = thumbnailKey(manifest, selection);
  for (const field of Object.keys(AVATAR_OPTIONS).concat('presetId')) {
    assert.notEqual(thumbnailKey(manifest, { ...selection, [field]: selection[field] + '-changed' }), key);
  }
  assert.notEqual(thumbnailKey({ ...manifest, revision: 'changed' }, selection), key);
  assert.equal(thumbnailKey(manifest, Object.fromEntries(Object.entries(selection).reverse())), key);
});

test('cache keys invalidate camera, asset and resolved appearance binding changes', () => {
  const manifest = fixture();
  const selection = Object.fromEntries(Object.entries(AVATAR_OPTIONS).map(([key, options]) => [key, options[0].value]));
  selection.presetId = 'M01';
  const key = thumbnailKey(manifest, selection);
  for (const mutate of [
    next => { next.bodies.male.camera.fov = 40; },
    next => { next.bodies.male.asset.sha256 = '2'.repeat(64); },
    next => { next.bodies.male.presets.M01.morphs[0].value = .77; },
    next => { next.bodies.male.wardrobe.hairColor.materials = ['new-hair']; },
  ]) {
    const next = copy(manifest); mutate(next); assert.notEqual(thumbnailKey(next, selection), key);
  }
});

test('staging permits pending art/browser review but never missing export proof', () => {
  const manifest = fixture();
  manifest.evidence.artReview = { accepted: false, reference: '' };
  manifest.evidence.browserReview = { accepted: false, reference: '' };
  assert.equal(validateProductionManifest(manifest).ready, false);
  assert.equal(validateProductionManifest(manifest, { mode: 'staging' }).ready, true);
  manifest.evidence.exportValidation.accepted = false;
  assert.equal(validateProductionManifest(manifest, { mode: 'staging' }).ready, false);
  assert.equal(validateProductionManifest(fixture(), { mode: 'other' }).ready, false);
});
