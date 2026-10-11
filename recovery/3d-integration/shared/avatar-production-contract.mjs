import { AVATAR_OPTIONS } from './avatar.js';
import { CHARACTERS } from './characters.ts';

export const THREE_VERSION = '0.180.0';
export const PRODUCTION_RENDER_REVISION = 'three-r180-studio-v1';
export const ANIMATION_NAMES = Object.freeze(['idle', 'wave', 'celebrate']);
export const GEOMETRY_FIELDS = Object.freeze(['hairStyle', 'shirtStyle', 'bottomStyle', 'hatStyle']);
export const COLOR_FIELDS = Object.freeze(['skinTone', 'hairColor', 'shirtColor', 'bottomColor', 'shoeColor', 'hatColor']);
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const sorted = value => Array.isArray(value) ? value.map(sorted) : record(value)
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, sorted(value[key])])) : value;
export const stableJson = value => JSON.stringify(sorted(value));

export class AssetCapabilityError extends Error {
  constructor(issues) {
    super('Production avatar assets are not ready: ' + issues.join('; '));
    this.name = 'AssetCapabilityError';
    this.issues = [...issues];
  }
}

export function stateTargets(state) {
  if (!record(state)) return [];
  return [
    ...Object.keys(record(state.visibility) ? state.visibility : {}).map(name => 'visible:' + name),
    ...(Array.isArray(state.morphs) ? state.morphs : []).filter(record).map(item => 'morph:' + item.mesh + ':' + item.target),
  ].sort();
}

function geometrySignature(state) {
  return stableJson({
    visibility: state?.visibility,
    morphs: (Array.isArray(state?.morphs) ? state.morphs : []).filter(record)
      .map(({ mesh, target, value }) => ({ mesh, target, value }))
      .sort((a, b) => (a.mesh + ':' + a.target).localeCompare(b.mesh + ':' + b.target)),
  });
}

export function validateProductionManifest(manifest, options = {}) {
  const issues = [];
  const require = (ok, message) => { if (!ok) issues.push(message); };
  if (!record(manifest)) return { ready: false, issues: ['Manifest is absent; the legacy renderer remains active.'] };
  require(manifest.schemaVersion === 1, 'schemaVersion must be 1');
  require(typeof manifest.revision === 'string' && /^[A-Za-z0-9._-]{1,80}$/.test(manifest.revision), 'Invalid asset revision');
  require(manifest.threeVersion === THREE_VERSION, 'Manifest renderer version differs from the pinned runtime');
  require(record(manifest.evidence), 'Missing export/review evidence');
  require(options.mode === undefined || options.mode === 'production' || options.mode === 'staging', 'Invalid validation mode');
  for (const review of ['exportValidation', 'artReview', 'browserReview']) {
    const item = manifest.evidence?.[review];
    const approvalRequired = options.mode !== 'staging' || review === 'exportValidation';
    require(record(item) && typeof item.accepted === 'boolean' && typeof item.reference === 'string'
      && (!approvalRequired || (item.accepted === true && item.reference.length > 0)),
      'Missing accepted ' + review + ' evidence');
  }
  require(record(manifest.bodies), 'Missing male/female asset specifications');
  const canonicalIds = CHARACTERS.map(p => p.id).sort();
  const seenIds = [];
  for (const gender of ['male', 'female']) {
    const body = manifest.bodies?.[gender];
    if (!record(body)) { issues.push('Missing ' + gender + ' body'); continue; }
    const asset = body.asset;
    require(record(asset), gender + ': missing asset');
    if (record(asset)) {
      require(typeof asset.url === 'string' && /^\/avatars\/production\/[A-Za-z0-9_./-]+\.glb$/.test(asset.url)
        && !asset.url.includes('..') && !asset.url.includes('//'), gender + ': asset URL must be an approved same-origin GLB');
      require(typeof asset.sha256 === 'string' && /^[a-f0-9]{64}$/.test(asset.sha256), gender + ': missing SHA-256');
      require(Number.isInteger(asset.byteLength) && asset.byteLength > 20 && asset.byteLength <= 33554432, gender + ': invalid GLB byte limit');
      require(typeof asset.rigRoot === 'string' && asset.rigRoot.length > 0, gender + ': missing rig root name');
      require(Number.isFinite(asset.scale) && asset.scale > 0 && asset.scale <= 100, gender + ': invalid scale');
      require(Number.isFinite(asset.rotationY), gender + ': invalid model rotation');
    }
    const camera = body.camera;
    const vector = v => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite);
    require(record(camera) && vector(camera.position) && vector(camera.target) && Number.isFinite(camera.fov)
      && camera.fov > 5 && camera.fov < 100 && Number.isFinite(camera.near) && Number.isFinite(camera.far) && camera.near > 0 && camera.far > camera.near
      && vector(camera.position) && vector(camera.target)
      && camera.position.some((v, i) => v !== camera.target[i]), gender + ': invalid studio camera');
    const owners = new Map();
    function claim(targets, field) {
      for (const target of targets) {
        const previous = owners.get(target);
        if (previous && previous !== field) issues.push(gender + ': ' + target + ' is shared by ' + previous + ' and ' + field);
        owners.set(target, field);
      }
    }
    function checkState(state, label) {
      if (!record(state) || !record(state.visibility) || !Array.isArray(state.morphs)) {
        issues.push(gender + ': invalid geometry state ' + label); return [];
      }
      for (const [name, visible] of Object.entries(state.visibility)) {
        require(name.length > 0 && typeof visible === 'boolean', gender + ': invalid visibility in ' + label);
      }
      const targets = new Set();
      for (const item of state.morphs) {
        require(record(item) && typeof item.mesh === 'string' && item.mesh.length > 0
          && typeof item.target === 'string' && item.target.length > 0 && Number.isFinite(item.value)
          && item.value >= -2 && item.value <= 2, gender + ': invalid morph in ' + label);
        const key = item?.mesh + ':' + item?.target;
        require(!targets.has(key), gender + ': duplicate morph in ' + label); targets.add(key);
      }
      require(stateTargets(state).length > 0, gender + ': ' + label + ' has no geometry targets');
      return stateTargets(state);
    }
    const presets = body.presets;
    require(record(presets), gender + ': missing identity presets');
    const expectedIds = CHARACTERS.filter(p => p.gender === gender).map(p => p.id).sort();
    const actualIds = record(presets) ? Object.keys(presets).sort() : [];
    require(stableJson(actualIds) === stableJson(expectedIds), gender + ': identity IDs must exactly match the ten canonical presets');
    seenIds.push(...actualIds);
    let identityTargets;
    const signatures = new Set();
    for (const id of actualIds) {
      const state = presets[id];
      const targets = checkState(state, id);
      const signature = geometrySignature(state);
      require(!signatures.has(signature), gender + ': duplicate identity geometry state for ' + id);
      signatures.add(signature);
      if (identityTargets) require(stableJson(targets) === stableJson(identityTargets), gender + ': identity target coverage differs for ' + id);
      identityTargets ||= targets;
    }
    claim(identityTargets || [], 'identity');
    require(record(body.wardrobe), gender + ': missing wardrobe bindings');
    for (const field of [...GEOMETRY_FIELDS, ...COLOR_FIELDS]) {
      const binding = body.wardrobe?.[field];
      const expected = AVATAR_OPTIONS[field].map(o => o.value).sort();
      const actual = record(binding?.choices) ? Object.keys(binding.choices).sort() : [];
      require(stableJson(actual) === stableJson(expected), gender + ': incomplete enum coverage for ' + field);
      if (GEOMETRY_FIELDS.includes(field)) {
        require(binding?.kind === 'geometry', gender + ': ' + field + ' must change authored geometry');
        let previousTargets;
        const geometryStates = new Set();
        for (const value of actual) {
          const targets = checkState(binding.choices[value], field + '=' + value);
          if (previousTargets) require(stableJson(targets) === stableJson(previousTargets), gender + ': geometry target coverage differs for ' + field);
          previousTargets ||= targets;
          const signature = geometrySignature(binding.choices[value]);
          require(!geometryStates.has(signature), gender + ': duplicate geometry choice for ' + field + '=' + value);
          geometryStates.add(signature);
        }
        claim(previousTargets || [], field);
      } else {
        require(binding?.kind === 'color' && Array.isArray(binding.materials) && binding.materials.length > 0
          && binding.materials.every(v => typeof v === 'string' && v.length > 0)
          && new Set(binding.materials).size === binding.materials.length, gender + ': invalid material targets for ' + field);
        for (const option of AVATAR_OPTIONS[field]) {
          const value = binding?.choices?.[option.value];
          require(typeof value === 'string' && value.toLowerCase() === option.color?.toLowerCase(),
            gender + ': ' + field + '=' + option.value + ' differs from the canonical palette');
        }
        claim((Array.isArray(binding?.materials) ? binding.materials : []).map(name => 'color:' + name), field);
      }
    }
    require(record(body.clips), gender + ': missing animation mappings');
    for (const name of ANIMATION_NAMES) require(typeof body.clips?.[name] === 'string'
      && body.clips[name].length > 0, gender + ': missing ' + name + ' clip');
    require(new Set(ANIMATION_NAMES.map(name => body.clips?.[name])).size === ANIMATION_NAMES.length,
      gender + ': animation mappings must be three distinct exported clips');
  }
  require(stableJson(seenIds.sort()) === stableJson(canonicalIds), 'The catalogue must cover exactly 20 canonical identities');
  return { ready: issues.length === 0, issues };
}

export function assertProductionManifest(manifest, options = {}) {
  const result = validateProductionManifest(manifest, options);
  if (!result.ready) throw new AssetCapabilityError(result.issues);
  return manifest;
}

export function thumbnailKey(manifest, selection) {
  const body = manifest.bodies?.[selection.bodyStyle];
  const bindings = body ? {
    asset: body.asset, camera: body.camera, identity: body.presets?.[selection.presetId],
    geometry: Object.fromEntries(GEOMETRY_FIELDS.map(field => [field, body.wardrobe?.[field]?.choices?.[selection[field]]])),
    color: Object.fromEntries(COLOR_FIELDS.map(field => [field, {
      materials: body.wardrobe?.[field]?.materials, value: body.wardrobe?.[field]?.choices?.[selection[field]],
    }])),
  } : null;
  return PRODUCTION_RENDER_REVISION + ':' + manifest.revision + ':' + stableJson(bindings) + ':' +
    Object.keys(AVATAR_OPTIONS).concat('presetId').sort().map(key => key + '=' + selection[key]).join('|');
}
