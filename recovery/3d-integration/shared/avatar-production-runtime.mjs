import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';
import { normalizeWardrobe } from './avatar-registry.ts';
import {
  ANIMATION_NAMES, GEOMETRY_FIELDS, COLOR_FIELDS, AssetCapabilityError,
  assertProductionManifest, stableJson, thumbnailKey,
} from './avatar-production-contract.mjs';

const catalogs = new Map();
const pendingThumbnails = new Map();
const thumbnails = new Map();
const MAX_THUMBNAILS = 64;
const MAX_THUMBNAIL_BYTES = 16 * 1024 * 1024;
let thumbnailTail = Promise.resolve();
let thumbnailRenderer = null;
let thumbnailCanvas = null;
let thumbnailIdleTimer = null;
let thumbnailContextLost = false;
let activeHeroToken = null;

const abortError = () => new DOMException('Avatar request cancelled', 'AbortError');
const checkAbort = signal => { if (signal?.aborted) throw abortError(); };
const materialsOf = object => Array.isArray(object.material) ? object.material : object.material ? [object.material] : [];
const ancestorOf = (ancestor, object) => {
  for (let current = object; current; current = current.parent) if (current === ancestor) return true;
  return false;
};

function indexScene(scene) {
  const nodes = new Map(), materials = new Map();
  scene.traverse(object => {
    if (object.name) {
      const list = nodes.get(object.name) || [];
      list.push(object); nodes.set(object.name, list);
    }
    for (const material of materialsOf(object)) {
      if (!material.name) continue;
      const list = materials.get(material.name) || [];
      if (!list.includes(material)) list.push(material);
      materials.set(material.name, list);
    }
  });
  const node = name => {
    const matches = nodes.get(name);
    if (matches?.length !== 1) throw new AssetCapabilityError(['Missing or ambiguous scene node: ' + name]);
    return matches[0];
  };
  const material = name => {
    const matches = materials.get(name);
    if (matches?.length !== 1) throw new AssetCapabilityError(['Missing or ambiguous material: ' + name]);
    return matches[0];
  };
  return { node, material };
}

function inspectGlb(buffer) {
  const view = new DataView(buffer);
  if (buffer.byteLength < 20 || view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2
    || view.getUint32(8, true) !== buffer.byteLength) throw new AssetCapabilityError(['Invalid GLB header']);
  let offset = 12, json = null, chunks = 0, binaryChunks = 0;
  while (offset < buffer.byteLength) {
    if (offset + 8 > buffer.byteLength) throw new AssetCapabilityError(['Truncated GLB chunk']);
    const length = view.getUint32(offset, true), type = view.getUint32(offset + 4, true);
    offset += 8;
    if (length % 4 !== 0 || offset + length > buffer.byteLength) throw new AssetCapabilityError(['Invalid GLB chunk length']);
    if (chunks === 0 && type !== 0x4e4f534a) throw new AssetCapabilityError(['The first GLB chunk must be JSON']);
    if (type === 0x4e4f534a) {
      if (json) throw new AssetCapabilityError(['Duplicate JSON chunk']);
      json = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, offset, length)));
    } else if (type === 0x004e4942) binaryChunks++;
    else throw new AssetCapabilityError(['Unsupported GLB chunk']);
    chunks++; offset += length;
  }
  if (!json || json.asset?.version !== '2.0' || binaryChunks !== 1) throw new AssetCapabilityError(['Expected one self-contained glTF 2.0 binary']);
  if ((json.extensionsRequired || []).length) throw new AssetCapabilityError(['Required glTF extensions need an explicit, reviewed decoder contract']);
  if ((json.buffers || []).some(bufferSpec => bufferSpec.uri !== undefined)
    || (json.images || []).some(image => image.uri !== undefined || !Number.isInteger(image.bufferView)))
    throw new AssetCapabilityError(['External/data URI resources are not permitted in production GLBs']);
  for (const mesh of json.meshes || []) for (const primitive of mesh.primitives || []) {
    if ('JOINTS_1' in (primitive.attributes || {}) || 'WEIGHTS_1' in (primitive.attributes || {}))
      throw new AssetCapabilityError(['Export has extra skin influences unsupported by the standard Three shader']);
  }
  return json;
}

function hasMotion(track, property) {
  if (!track.times.length || !Array.from(track.times).every(Number.isFinite)
    || !Array.from(track.values).every(Number.isFinite)) return false;
  const interpolant = track.createInterpolant();
  const moments = new Set(track.times);
  for (let i = 1; i < track.times.length; i++) {
    if (track.times[i] <= track.times[i - 1]) return false;
    for (const part of [.25, .5, .75]) moments.add(track.times[i - 1] + (track.times[i] - track.times[i - 1]) * part);
  }
  let first;
  for (const time of moments) {
    const sample = Array.from(interpolant.evaluate(time));
    if (!sample.every(Number.isFinite)) return false;
    if (property === 'quaternion') {
      if (sample.length !== 4) return false;
      const length = Math.hypot(...sample);
      if (length < 1e-12) return false;
      for (let i = 0; i < 4; i++) sample[i] /= length;
    }
    if (!first) { first = sample; continue; }
    const same = sample.every((v, i) => Math.abs(v - first[i]) < 1e-6);
    const opposite = property === 'quaternion' && sample.every((v, i) => Math.abs(v + first[i]) < 1e-6);
    if (!same && !opposite) return true;
  }
  return false;
}

function validateLoadedAsset(gltf, body) {
  const index = indexScene(gltf.scene), root = index.node(body.asset.rigRoot);
  const usedBones = new Set(), skeletons = new Set();
  gltf.scene.traverse(object => {
    if (!object.isSkinnedMesh) return;
    skeletons.add(object.skeleton);
    const indices = object.geometry.getAttribute('skinIndex'), weights = object.geometry.getAttribute('skinWeight');
    if (!indices || !weights || indices.itemSize !== 4 || weights.itemSize !== 4 || indices.count !== weights.count)
      throw new AssetCapabilityError(['Every skinned mesh needs four complete skin indices/weights']);
    for (const bone of object.skeleton.bones) if (!ancestorOf(root, bone))
      throw new AssetCapabilityError(['The cloned rig root does not contain all skeleton bones']);
    for (let vertex = 0; vertex < indices.count; vertex++) {
      let total = 0; const positive = new Set();
      for (let component = 0; component < 4; component++) {
        const weight = weights.getComponent(vertex, component), joint = indices.getComponent(vertex, component);
        if (!Number.isFinite(weight) || weight < 0 || !Number.isInteger(joint) || joint < 0 || joint >= object.skeleton.bones.length)
          throw new AssetCapabilityError(['Invalid skin influence']);
        total += weight;
        if (weight > 0) {
          if (positive.has(joint)) throw new AssetCapabilityError(['Duplicate positive joint influence']);
          positive.add(joint); usedBones.add(object.skeleton.bones[joint]);
        }
      }
      if (Math.abs(total - 1) > 1e-4) throw new AssetCapabilityError(['Skin weights do not sum to one']);
    }
  });
  if (!usedBones.size || !skeletons.size) throw new AssetCapabilityError(['The export has no deforming skeleton']);
  const morphChecks = new Set();
  const inspectState = state => {
    for (const name of Object.keys(state.visibility)) {
      const object = index.node(name);
      if (!object.isMesh || !object.geometry.getAttribute('position')?.count)
        throw new AssetCapabilityError(['Geometry visibility must target an actual mesh: ' + name]);
    }
    for (const item of state.morphs) {
      const key = item.mesh + ':' + item.target;
      if (morphChecks.has(key)) continue;
      const object = index.node(item.mesh), morph = object.morphTargetDictionary?.[item.target];
      const positions = object.geometry?.morphAttributes?.position?.[morph];
      if (!object.isMesh || !Number.isInteger(morph) || !positions || !object.morphTargetInfluences
        || positions.count !== object.geometry.getAttribute('position')?.count)
        throw new AssetCapabilityError(['Missing geometry morph target: ' + key]);
      let changesGeometry = false;
      const base = object.geometry.getAttribute('position');
      for (let i = 0; i < positions.count; i++) for (let c = 0; c < 3; c++) {
        const value = positions.getComponent(i, c);
        if (!Number.isFinite(value)) throw new AssetCapabilityError(['Non-finite morph geometry: ' + key]);
        const delta = object.geometry.morphTargetsRelative ? value : value - base.getComponent(i, c);
        if (Math.abs(delta) > 1e-6) changesGeometry = true;
      }
      if (!changesGeometry) throw new AssetCapabilityError(['Identity/style morph does not change geometry: ' + key]);
      morphChecks.add(key);
    }
  };
  Object.values(body.presets).forEach(inspectState);
  for (const field of GEOMETRY_FIELDS) Object.values(body.wardrobe[field].choices).forEach(inspectState);
  for (const field of COLOR_FIELDS) for (const name of body.wardrobe[field].materials) {
    const material = index.material(name);
    if (!material.color || (!material.isMeshStandardMaterial && !material.isMeshPhysicalMaterial))
      throw new AssetCapabilityError(['Recoloring needs an authored independent PBR material: ' + name]);
  }
  const clips = new Map();
  for (const name of ANIMATION_NAMES) {
    const matches = gltf.animations.filter(clip => clip.name === body.clips[name]);
    if (matches.length !== 1 || !Number.isFinite(matches[0].duration) || matches[0].duration <= 0)
      throw new AssetCapabilityError(['Missing/ambiguous/empty exported animation: ' + name]);
    const clip = matches[0];
    const deforms = clip.tracks.some(track => {
      const binding = THREE.PropertyBinding.parseTrackName(track.name);
      if (!['position', 'quaternion', 'scale'].includes(binding.propertyName)) return false;
      const target = THREE.PropertyBinding.findNode(gltf.scene, binding.nodeName);
      if (!target?.isBone || !ancestorOf(root, target)) return false;
      // A wrapper/common root that carries the whole skin is global motion.
      const affected = [...usedBones].filter(bone => ancestorOf(target, bone));
      if (!affected.length || affected.length === usedBones.size) return false;
      return hasMotion(track, binding.propertyName);
    });
    if (!deforms) throw new AssetCapabilityError(['Animation has no changing local deforming joint: ' + name]);
    // GLTFLoader uses UUIDs for unnamed nodes. Those tracks cannot survive clone UUID changes.
    for (const track of clip.tracks) {
      const binding = THREE.PropertyBinding.parseTrackName(track.name);
      const target = THREE.PropertyBinding.findNode(gltf.scene, binding.nodeName);
      if (!target || !target.name || index.node(target.name) !== target)
        throw new AssetCapabilityError(['Animation target must have a unique retained node name: ' + track.name]);
    }
    clips.set(name, clip);
  }
  return { gltf, body, clips };
}

function disposeMaster(gltf) {
  const geometries = new Set(), materials = new Set(), textures = new Set(), images = new Set(), skeletons = new Set();
  for (const scene of gltf.scenes || [gltf.scene]) scene.traverse(object => {
    if (object.geometry) geometries.add(object.geometry);
    if (object.skeleton) skeletons.add(object.skeleton);
    for (const material of materialsOf(object)) materials.add(material);
  });
  for (const material of materials) for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
  for (const texture of textures) {
    const image = texture.source?.data;
    if (Array.isArray(image)) image.forEach(item => images.add(item)); else if (image) images.add(image);
    texture.dispose();
  }
  for (const geometry of geometries) geometry.dispose();
  for (const material of materials) material.dispose();
  for (const skeleton of skeletons) skeleton.dispose();
  for (const image of images) if (typeof image?.close === 'function') image.close();
}

async function loadBody(body) {
  const response = await fetch(body.asset.url, { credentials: 'same-origin' });
  if (!response.ok) throw new AssetCapabilityError(['GLB download failed: HTTP ' + response.status]);
  const advertised = Number(response.headers.get('content-length'));
  if (advertised && advertised !== body.asset.byteLength) throw new AssetCapabilityError(['GLB content length differs from its reviewed export']);
  const buffer = await response.arrayBuffer();
  if (buffer.byteLength !== body.asset.byteLength) throw new AssetCapabilityError(['GLB byte length differs from its reviewed export']);
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer)),
    byte => byte.toString(16).padStart(2, '0')).join('');
  if (digest !== body.asset.sha256) throw new AssetCapabilityError(['GLB SHA-256 differs from its reviewed export']);
  inspectGlb(buffer);
  const gltf = await new GLTFLoader().parseAsync(buffer, '');
  try { return validateLoadedAsset(gltf, body); }
  catch (error) { disposeMaster(gltf); throw error; }
}

function trimCatalogs(protectedCatalog = null) {
  if (catalogs.size <= 2) return;
  const candidates = [...catalogs.entries()].filter(([, entry]) => entry.catalog && entry.catalog !== protectedCatalog && entry.catalog.refs === 0 && entry.requests === 0)
    .sort((a, b) => a[1].catalog.lastUsed - b[1].catalog.lastUsed);
  for (const [key, entry] of candidates) {
    if (catalogs.size <= 2) break;
    Object.values(entry.catalog.bodies).forEach(master => disposeMaster(master.gltf));
    catalogs.delete(key);
  }
}

async function acquireCatalog(manifest, mode = 'production') {
  assertProductionManifest(manifest, { mode });
  const key = stableJson(manifest);
  let entry = catalogs.get(key);
  if (!entry) {
    entry = { catalog: null, promise: null, requests: 0 };
    entry.promise = Promise.allSettled(['male', 'female'].map(gender => loadBody(manifest.bodies[gender])))
      .then(results => {
        const failure = results.find(result => result.status === 'rejected');
        if (failure) {
          for (const result of results) if (result.status === 'fulfilled') disposeMaster(result.value.gltf);
          throw failure.reason;
        }
        const catalog = { manifest, refs: 0, lastUsed: performance.now(),
          bodies: { male: results[0].value, female: results[1].value } };
        entry.catalog = catalog; trimCatalogs(catalog); return catalog;
      }).catch(error => { if (catalogs.get(key) === entry) catalogs.delete(key); throw error; });
    catalogs.set(key, entry);
  }
  entry.requests++;
  try {
    const catalog = await entry.promise;
    catalog.refs++; catalog.lastUsed = performance.now();
    return catalog;
  } finally { entry.requests--; }
}

function releaseCatalog(catalog) {
  catalog.refs--; catalog.lastUsed = performance.now(); trimCatalogs();
}

/** A warm catalogue lease; callers must release it. Hero/thumbnail factories own theirs. */
export async function prepareProductionCatalog(manifest, options = {}) {
  const catalog = await acquireCatalog(manifest, options.mode);
  let released = false;
  return { revision: manifest.revision, mode: options.mode || 'production', release() {
    if (released) return; released = true; releaseCatalog(catalog);
  } };
}

function instantiate(catalog, selection) {
  const normalized = normalizeWardrobe(selection);
  const master = catalog.bodies[normalized.bodyStyle];
  const root = cloneSkeleton(master.gltf.scene);
  const ownedMaterials = new Set(), ownedSkeletons = new Set(), materialCopies = new Map();
  root.traverse(object => {
    if (object.isSkinnedMesh) {
      ownedSkeletons.add(object.skeleton);
      // Skinned bounds vary with poses. Disable frustum culling, not skinning.
      object.frustumCulled = false;
    }
    if (object.material) {
      const copies = materialsOf(object).map(material => {
        if (!materialCopies.has(material)) {
          const copy = material.clone(); materialCopies.set(material, copy); ownedMaterials.add(copy);
        }
        return materialCopies.get(material);
      });
      object.material = Array.isArray(object.material) ? copies : copies[0];
    }
  });
  const index = indexScene(root), mixer = new THREE.AnimationMixer(root);
  const stage = new THREE.Group(); stage.add(root);
  root.scale.multiplyScalar(master.body.asset.scale);
  root.rotation.y += master.body.asset.rotationY;
  let disposed = false, selectionNow = normalized, ownedMorphs = [], currentAction = null;
  catalog.lastUsed = performance.now();
  const applyState = state => {
    for (const [name, visible] of Object.entries(state.visibility)) index.node(name).visible = visible;
    for (const item of state.morphs) {
      const object = index.node(item.mesh), target = object.morphTargetDictionary[item.target];
      object.morphTargetInfluences[target] = item.value;
      ownedMorphs.push([object, target, item.value]);
    }
  };
  const restoreOwnedMorphs = () => {
    for (const [object, target, value] of ownedMorphs) object.morphTargetInfluences[target] = value;
  };
  const actions = Object.fromEntries(ANIMATION_NAMES.map(name => [name, mixer.clipAction(master.clips.get(name))]));
  const play = (name = 'idle') => {
    if (disposed) return;
    const next = actions[name];
    if (!next) throw new AssetCapabilityError(['Unmapped animation requested: ' + name]);
    next.reset().setEffectiveTimeScale(1).setEffectiveWeight(1);
    next.setLoop(name === 'idle' ? THREE.LoopRepeat : THREE.LoopOnce, name === 'idle' ? Infinity : 1);
    next.clampWhenFinished = name !== 'idle';
    if (currentAction && currentAction !== next) {
      currentAction.fadeOut(.18); next.fadeIn(.18);
    }
    next.play(); currentAction = next;
  };
  const finished = event => { if (event.action === currentAction && currentAction !== actions.idle) play('idle'); };
  mixer.addEventListener('finished', finished);
  const updateSelection = nextValue => {
    if (disposed) throw new Error('Avatar instance is disposed');
    const next = normalizeWardrobe(nextValue);
    if (next.bodyStyle !== normalized.bodyStyle) throw new AssetCapabilityError(['Changing body rig requires a new instance']);
    ownedMorphs = [];
    applyState(master.body.presets[next.presetId]);
    for (const field of GEOMETRY_FIELDS) applyState(master.body.wardrobe[field].choices[next[field]]);
    for (const field of COLOR_FIELDS) {
      const binding = master.body.wardrobe[field];
      for (const name of binding.materials) index.material(name).color.set(binding.choices[next[field]]);
    }
    selectionNow = next; root.updateMatrixWorld(true);
  };
  try { updateSelection(normalized); }
  catch (error) {
    mixer.stopAllAction(); mixer.uncacheRoot(root);
    ownedMaterials.forEach(material => material.dispose()); ownedSkeletons.forEach(skeleton => skeleton.dispose());
    throw error;
  }
  return {
    root: stage, body: master.body,
    get selection() { return selectionNow; },
    updateSelection, play,
    update(delta) { mixer.update(Math.min(Math.max(delta, 0), .05)); restoreOwnedMorphs(); root.updateMatrixWorld(true); },
    neutral() {
      mixer.stopAllAction(); currentAction = null;
      actions.idle.reset().play(); mixer.setTime(0); actions.idle.paused = true; restoreOwnedMorphs(); root.updateMatrixWorld(true);
    },
    dispose() {
      if (disposed) return; disposed = true;
      mixer.removeEventListener('finished', finished); mixer.stopAllAction(); mixer.uncacheRoot(root);
      ownedMaterials.forEach(material => material.dispose()); ownedSkeletons.forEach(skeleton => skeleton.dispose());
      stage.remove(root); releaseCatalog(catalog);
    },
  };
}

function studio(body) {
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xf1f5ff, 0x586b75, 2));
  const key = new THREE.DirectionalLight(0xfff4e5, 3); key.position.set(-3, 5, 4); scene.add(key);
  const fill = new THREE.DirectionalLight(0xd6e7ff, 1.2); fill.position.set(3, 3, -2); scene.add(fill);
  const spec = body.camera;
  const camera = new THREE.PerspectiveCamera(spec.fov, .75, spec.near, spec.far);
  camera.position.fromArray(spec.position); camera.lookAt(new THREE.Vector3().fromArray(spec.target));
  return { scene, camera };
}

function rendererFor(canvas, thumbnail = false) {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true,
    preserveDrawingBuffer: thumbnail, powerPreference: 'default' });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1;
  return renderer;
}

export async function createProductionHero(canvas, selection, options) {
  checkAbort(options.signal);
  if (typeof document === 'undefined' || typeof ResizeObserver === 'undefined' || typeof matchMedia === 'undefined')
    throw new AssetCapabilityError(['The browser lacks the required avatar rendering lifecycle APIs']);
  const catalog = await acquireCatalog(options.manifest, options.mode);
  let instance;
  try { checkAbort(options.signal); instance = instantiate(catalog, selection); }
  catch (error) { releaseCatalog(catalog); throw error; }
  if (activeHeroToken) { instance.dispose(); throw new AssetCapabilityError(['Only one interactive production avatar canvas is permitted']); }
  const heroToken = {};
  let renderer;
  try { renderer = rendererFor(canvas); activeHeroToken = heroToken; }
  catch (error) { instance.dispose(); throw error; }
  const { scene, camera } = studio(instance.body); scene.add(instance.root);
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  let disposed = false, lost = false, visible = options.visible !== false, motion = options.motion !== false;
  let angle = -.12, frame = 0, previous = 0, lastDraw = 0, dragging = false, pointerId = null, lastX = 0;
  const draw = () => {
    if (disposed || lost) return;
    instance.root.rotation.y = angle; renderer.render(scene, camera);
  };
  const enabled = () => !disposed && !lost && visible && !document.hidden && motion && !media.matches;
  const tick = time => {
    frame = 0; if (!enabled()) return;
    if (!previous) previous = time;
    if (time - lastDraw >= 1000 / 30) {
      instance.update((time - previous) / 1000); previous = time; lastDraw = time; draw();
    }
    frame = requestAnimationFrame(tick);
  };
  const reconcile = () => {
    if (!enabled()) { cancelAnimationFrame(frame); frame = 0; previous = 0; if (!lost) draw(); }
    else if (!frame) { previous = 0; lastDraw = 0; frame = requestAnimationFrame(tick); }
  };
  const resize = () => {
    if (disposed || lost) return;
    const bounds = canvas.getBoundingClientRect();
    if (bounds.width <= 0 || bounds.height <= 0) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(bounds.width, bounds.height, false);
    camera.aspect = bounds.width / bounds.height; camera.updateProjectionMatrix(); draw();
  };
  const resizeObserver = new ResizeObserver(resize); resizeObserver.observe(canvas);
  const lostHandler = event => {
    event.preventDefault(); lost = true; cancelAnimationFrame(frame); frame = 0; previous = 0;
    options.onState?.('context-lost');
  };
  const restoredHandler = () => {
    lost = false; options.onState?.('ready'); resize(); reconcile();
  };
  const down = event => {
    if (disposed || lost || !event.isPrimary || event.button !== 0) return;
    dragging = true; pointerId = event.pointerId; lastX = event.clientX;
    try { canvas.setPointerCapture(event.pointerId); } catch { /* Pointer may have ended. */ }
  };
  const move = event => {
    if (!dragging || event.pointerId !== pointerId) return;
    angle += (event.clientX - lastX) * .012; lastX = event.clientX; draw();
  };
  const up = event => {
    if (event.pointerId !== pointerId) return;
    dragging = false;
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    pointerId = null;
  };
  canvas.addEventListener('webglcontextlost', lostHandler);
  canvas.addEventListener('webglcontextrestored', restoredHandler);
  canvas.addEventListener('pointerdown', down); canvas.addEventListener('pointermove', move);
  canvas.addEventListener('pointerup', up); canvas.addEventListener('pointercancel', up); canvas.addEventListener('lostpointercapture', up);
  document.addEventListener('visibilitychange', reconcile); media.addEventListener('change', reconcile);
  const dispose = () => {
    if (disposed) return; disposed = true;
    cancelAnimationFrame(frame); resizeObserver.disconnect();
    document.removeEventListener('visibilitychange', reconcile); media.removeEventListener('change', reconcile);
    canvas.removeEventListener('webglcontextlost', lostHandler); canvas.removeEventListener('webglcontextrestored', restoredHandler);
    canvas.removeEventListener('pointerdown', down); canvas.removeEventListener('pointermove', move);
    canvas.removeEventListener('pointerup', up); canvas.removeEventListener('pointercancel', up); canvas.removeEventListener('lostpointercapture', up);
    options.signal?.removeEventListener('abort', dispose);
    scene.remove(instance.root); instance.dispose(); renderer.dispose();
    if (!canvas.isConnected) renderer.forceContextLoss();
    if (activeHeroToken === heroToken) activeHeroToken = null;
  };
  options.signal?.addEventListener('abort', dispose, { once: true });
  try {
    instance.play('idle'); instance.update(0); resize(); options.onState?.('ready'); reconcile();
    checkAbort(options.signal);
  } catch (error) { dispose(); throw error; }
  return {
    updateSelection(next) { instance.updateSelection(next); draw(); },
    play(name) { if (motion && !media.matches) { instance.play(name); reconcile(); } },
    rotate(delta) { if (!disposed && Number.isFinite(delta)) { angle += delta; draw(); } },
    setMotion(value) { motion = value; reconcile(); },
    setVisible(value) { visible = value; reconcile(); },
    dispose,
  };
}

function destroyThumbnailRenderer() {
  if (thumbnailIdleTimer) clearTimeout(thumbnailIdleTimer);
  thumbnailIdleTimer = null;
  if (thumbnailRenderer) { thumbnailRenderer.dispose(); thumbnailRenderer.forceContextLoss(); }
  thumbnailRenderer = null; thumbnailCanvas = null; thumbnailContextLost = false;
}

async function renderThumbnailBlob(manifest, selection, mode) {
  const catalog = await acquireCatalog(manifest, mode);
  let instance;
  try { instance = instantiate(catalog, selection); }
  catch (error) { releaseCatalog(catalog); throw error; }
  try {
    if (thumbnailContextLost) destroyThumbnailRenderer();
    if (!thumbnailRenderer) {
      thumbnailCanvas = document.createElement('canvas');
      thumbnailCanvas.addEventListener('webglcontextlost', event => { event.preventDefault(); thumbnailContextLost = true; });
      thumbnailRenderer = rendererFor(thumbnailCanvas, true);
    }
    if (thumbnailIdleTimer) clearTimeout(thumbnailIdleTimer);
    const { scene, camera } = studio(instance.body);
    scene.add(instance.root); instance.root.rotation.y = -.12; instance.neutral();
    thumbnailRenderer.setPixelRatio(1); thumbnailRenderer.setSize(240, 320, false);
    camera.aspect = .75; camera.updateProjectionMatrix();
    if (thumbnailContextLost) throw new AssetCapabilityError(['Thumbnail WebGL context was lost']);
    thumbnailRenderer.render(scene, camera);
    const blob = await new Promise((resolve, reject) => thumbnailCanvas.toBlob(
      value => value && !thumbnailContextLost ? resolve(value) : reject(new AssetCapabilityError(['Thumbnail capture failed'])), 'image/png'));
    return blob;
  } finally {
    instance.dispose();
    thumbnailIdleTimer = setTimeout(destroyThumbnailRenderer, 30000);
  }
}

function pruneThumbnails() {
  let bytes = [...thumbnails.values()].reduce((total, entry) => total + entry.blob.size, 0);
  const evictable = [...thumbnails.entries()].filter(([, entry]) => entry.refs === 0)
    .sort((a, b) => a[1].used - b[1].used);
  for (const [key, entry] of evictable) {
    if (thumbnails.size <= MAX_THUMBNAILS && bytes <= MAX_THUMBNAIL_BYTES) break;
    URL.revokeObjectURL(entry.url); bytes -= entry.blob.size; thumbnails.delete(key);
  }
}

export async function acquireProductionThumbnail(selection, options) {
  assertProductionManifest(options.manifest, { mode: options.mode }); checkAbort(options.signal);
  const normalized = normalizeWardrobe(selection), key = thumbnailKey(options.manifest, normalized);
  let entry = thumbnails.get(key);
  if (!entry) {
    let job = pendingThumbnails.get(key);
    if (!job) {
      job = { waiters: 0, promise: null };
      job.promise = thumbnailTail.catch(() => {}).then(async () => {
        if (!job.waiters) throw abortError();
        return renderThumbnailBlob(options.manifest, normalized, options.mode);
      }).finally(() => { if (pendingThumbnails.get(key) === job) pendingThumbnails.delete(key); });
      thumbnailTail = job.promise.then(() => {}, () => {});
      pendingThumbnails.set(key, job);
    }
    job.waiters++;
    const blob = await new Promise((resolve, reject) => {
      let counted = true, settled = false;
      const leave = () => { if (counted) { counted = false; job.waiters--; } };
      const abort = () => {
        if (settled) return; settled = true; leave();
        options.signal?.removeEventListener('abort', abort); reject(abortError());
      };
      options.signal?.addEventListener('abort', abort, { once: true });
      if (options.signal?.aborted) abort();
      job.promise.then(value => {
        if (settled) return; settled = true; leave();
        options.signal?.removeEventListener('abort', abort); resolve(value);
      }, error => {
        if (settled) return; settled = true; leave();
        options.signal?.removeEventListener('abort', abort); reject(error);
      });
    });
    checkAbort(options.signal);
    entry = thumbnails.get(key);
    if (!entry) {
      entry = { blob, url: URL.createObjectURL(blob), refs: 0, used: performance.now() };
      thumbnails.set(key, entry);
    }
  }
  checkAbort(options.signal);
  entry.refs++; entry.used = performance.now(); pruneThumbnails();
  let released = false;
  const release = () => {
    if (released) return; released = true; entry.refs--; entry.used = performance.now();
    options.signal?.removeEventListener('abort', release); pruneThumbnails();
  };
  options.signal?.addEventListener('abort', release, { once: true });
  return { url: entry.url, release };
}

/** Clear only unleased previews and unowned masters; live instances retain ownership. */
export function disposeUnusedProductionResources() {
  for (const [key, entry] of thumbnails) if (!entry.refs) { URL.revokeObjectURL(entry.url); thumbnails.delete(key); }
  destroyThumbnailRenderer();
  for (const [key, entry] of catalogs) if (entry.catalog && entry.catalog.refs === 0 && entry.requests === 0) {
    Object.values(entry.catalog.bodies).forEach(master => disposeMaster(master.gltf)); catalogs.delete(key);
  }
}
