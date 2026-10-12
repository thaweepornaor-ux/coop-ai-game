/** Optional eyewear choices for the cooperative game avatar.
 * Pure helper: no changes to 15-question game, room, or persistence.
 * Visual adapter is intentionally separate from the 3D renderer.
 */
export const EYEWEAR_OPTIONS = Object.freeze([
  Object.freeze({ value: 'none', label: 'ไม่ใส่แว่น' }),
  Object.freeze({ value: 'round', label: 'แว่นทรงกลม' }),
  Object.freeze({ value: 'rectangle', label: 'แว่นทรงเหลี่ยม' }),
  Object.freeze({ value: 'aviator', label: 'แว่นทรงนักบิน' }),
]);
const accepted = new Set(EYEWEAR_OPTIONS.map(option => option.value));
export function normalizeEyewear(value) {
  return typeof value === 'string' && accepted.has(value) ? value : 'none';
}
/** Sanitized, front-facing SVG layer. Safe to combine with a 2D avatar preview. */
export function eyewearSvg(value) {
  switch (normalizeEyewear(value)) {
    case 'round':
      return '<g fill="none" stroke="#35373C" stroke-width="2.6"><circle cx="69" cy="63" r="7"/><circle cx="91" cy="63" r="7"/><path d="M76 62Q80 59 84 62M62 61L56 59M98 61L104 59"/></g>';
    case 'rectangle':
      return '<g fill="none" stroke="#34363A" stroke-width="2.5" stroke-linejoin="round"><rect x="61" y="57" width="16" height="12" rx="3"/><rect x="83" y="57" width="16" height="12" rx="3"/><path d="M77 61Q80 59 83 61M61 60L56 58M99 60L104 58"/></g>';
    case 'aviator':
      return '<g fill="rgba(112,162,180,.12)" stroke="#95784E" stroke-width="2" stroke-linejoin="round"><path d="M61 58Q69 55 77 58L76 66Q69 75 62 67Z"/><path d="M83 58Q91 55 99 58L98 67Q91 75 84 66Z"/><path d="M77 60Q80 58 83 60M61 60L56 57M99 60L104 57" fill="none"/></g>';
    default: return '';
  }
}
