'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { normalizeWardrobe } from '../../shared/avatar-registry';
import { thumbnailKey, validateProductionManifest } from '../../shared/avatar-production-contract.mjs';
import type { ProductionManifest } from '../../shared/avatar-production-contract.mjs';
import type { HeroController, ThumbnailLease } from '../../shared/avatar-production-runtime.mjs';
import type { AvatarProps } from './avatar';

/** Staging adapter: the public Avatar wrapper keeps this inactive until assets are accepted. */
export function ProductionAvatar({ options = {}, className, interactive = false, motion = true,
  animation = 'idle', manifest }: AvatarProps & { manifest: ProductionManifest }) {
  const container = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const hero = useRef<HeroController | null>(null);
  const [visible, setVisible] = useState(interactive);
  const [thumbnail, setThumbnail] = useState<{ key: string; url: string } | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'context-lost' | 'unavailable'>('loading');
  const [thumbnailFailed, setThumbnailFailed] = useState(false);
  const serialized = JSON.stringify(options);
  const selection = useMemo(() => {
    try { return normalizeWardrobe(JSON.parse(serialized)); } catch { return null; }
  }, [serialized]);
  const readiness = useMemo(() => validateProductionManifest(manifest), [manifest]);
  const selectionKey = selection ? thumbnailKey(manifest, selection as Parameters<typeof thumbnailKey>[1]) : '';
  const rig = selection?.bodyStyle || '';
  const latestSelection = useRef(selection), latestMotion = useRef(motion), latestAnimation = useRef(animation), latestVisible = useRef(visible);
  latestSelection.current = selection; latestMotion.current = motion; latestAnimation.current = animation; latestVisible.current = visible;

  useEffect(() => {
    if (!container.current) return;
    if (typeof IntersectionObserver === 'undefined') { setVisible(true); return; }
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { rootMargin: '120px' });
    observer.observe(container.current); return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || !selection || !readiness.ready) return;
    const abort = new AbortController();
    let lease: ThumbnailLease | undefined;
    setThumbnailFailed(false);
    import('../../shared/avatar-production-runtime.mjs')
      .then(runtime => runtime.acquireProductionThumbnail(selection, { manifest, signal: abort.signal }))
      .then(value => {
        lease = value;
        if (abort.signal.aborted) { value.release(); return; }
        setThumbnail({ key: selectionKey, url: value.url });
      })
      .catch(() => { if (!abort.signal.aborted) setThumbnailFailed(true); });
    return () => { abort.abort(); lease?.release(); };
  }, [manifest, selectionKey, visible, readiness.ready]);

  useEffect(() => {
    if (!interactive || !canvas.current || !latestSelection.current || !readiness.ready) return;
    const element = canvas.current, abort = new AbortController();
    let owned: HeroController | undefined;
    setStatus('loading');
    import('../../shared/avatar-production-runtime.mjs')
      .then(runtime => runtime.createProductionHero(element, latestSelection.current!, {
        manifest, signal: abort.signal, motion: latestMotion.current, visible: latestVisible.current,
        onState: state => { if (!abort.signal.aborted && latestSelection.current?.bodyStyle === rig) setStatus(state); },
      }))
      .then(controller => {
        owned = controller;
        if (abort.signal.aborted || latestSelection.current?.bodyStyle !== rig) { controller.dispose(); return; }
        hero.current = controller;
        if (latestSelection.current) controller.updateSelection(latestSelection.current);
        controller.setMotion(latestMotion.current); controller.setVisible(latestVisible.current);
        if (latestAnimation.current !== 'idle') controller.play(latestAnimation.current);
      })
      .catch(() => { if (!abort.signal.aborted) setStatus('unavailable'); });
    return () => {
      abort.abort(); owned?.dispose();
      if (hero.current === owned) hero.current = null;
    };
  }, [manifest, interactive, rig, readiness.ready]);

  useEffect(() => {
    if (!selection || !hero.current) return;
    try { hero.current.updateSelection(selection); }
    catch { setStatus('unavailable'); }
  }, [selectionKey]);
  useEffect(() => { hero.current?.setMotion(motion); }, [motion]);
  useEffect(() => { hero.current?.setVisible(visible); }, [visible]);
  useEffect(() => { hero.current?.play(animation); }, [animation]);

  const matchingThumbnail = thumbnail?.key === selectionKey ? thumbnail.url : '';
  const failed = !selection || !readiness.ready || (interactive ? status === 'unavailable' : thumbnailFailed);
  const showCanvas = interactive && status === 'ready' && !failed;
  return <div ref={container} className={className}
    data-avatar-renderer="production-three-r180"
    data-avatar-state={failed ? 'unavailable' : status}
    style={{ position: 'relative', aspectRatio: '3 / 4' }}>
    {matchingThumbnail && <img src={matchingThumbnail} alt="ตัวละครผู้เล่นตามชุดที่เลือก"
      decoding="async" loading="lazy" style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />}
    {interactive && <canvas key={rig + ':' + manifest.revision} ref={canvas} tabIndex={0}
      aria-label="ตัวละครสามมิติ ลากหรือกดลูกศรซ้ายขวาเพื่อหมุนดูชุด"
      onKeyDown={event => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault(); hero.current?.rotate(event.key === 'ArrowLeft' ? -.15 : .15);
        }
      }}
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', touchAction: 'pan-y',
        cursor: 'grab', opacity: showCanvas ? 1 : 0 }} />}
    {!matchingThumbnail && !showCanvas && <span role={failed ? 'status' : undefined}
      style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center',
        textAlign: 'center', padding: 8, fontSize: 12 }}>
      {failed ? 'ยังแสดงตัวละครไม่ได้ แต่เล่นเกมต่อได้' :
        status === 'context-lost' ? 'กำลังคืนภาพตัวละคร' : 'กำลังโหลดตัวละคร'}
    </span>}
  </div>;
}
