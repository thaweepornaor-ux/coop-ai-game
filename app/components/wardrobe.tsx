'use client';

import { useEffect, useId, useState } from 'react';
import { Avatar, AVATAR_OPTIONS, type AvatarOptionKey } from './avatar';
import { CHARACTERS, characterFor, type CharacterPreset } from '../../shared/characters';

const CATEGORIES: { label: string; short: string; style?: AvatarOptionKey; color: AvatarOptionKey; colorLabel: string; icon: string }[] = [
  { label: 'ตัวละคร', short: '01', style: 'bodyStyle', color: 'skinTone', colorLabel: 'โทนผิว', icon: 'body' },
  { label: 'ทรงผม', short: '02', style: 'hairStyle', color: 'hairColor', colorLabel: 'สีผม', icon: 'hair' },
  { label: 'เสื้อ', short: '03', style: 'shirtStyle', color: 'shirtColor', colorLabel: 'สีเสื้อ', icon: 'shirt' },
  { label: 'ท่อนล่าง', short: '04', style: 'bottomStyle', color: 'bottomColor', colorLabel: 'สีท่อนล่าง', icon: 'bottom' },
  { label: 'รองเท้า', short: '05', color: 'shoeColor', colorLabel: 'สีรองเท้า', icon: 'shoe' },
  { label: 'แว่นตา', short: '06', style: 'glassesStyle', color: 'glassesStyle', colorLabel: 'รูปแบบแว่น', icon: 'glasses' },
  { label: 'หมวก', short: '07', style: 'hatStyle', color: 'hatColor', colorLabel: 'สีหมวก', icon: 'hat' },
];

/** Item illustrations are selection icons, separate from the live 3D character. */
function ItemIcon({ kind, value = '', color = 'currentColor' }: { kind: string; value?: string; color?: string }) {
  let shape;
  if (kind === 'shirt') shape = <><path d="m19 15-11 9 7 10 6-4v23h22V30l6 4 7-10-11-9-8 4h-10z" fill={color} /><path d="M26 18q6 8 12 0" />{value !== 'tshirt' && <path d="m25 18 7 7 7-7M32 25v26" />}{value === 'jacket' && <path d="m25 18 4 15-8-3m18-12-4 15 8-3M23 43h5m8 0h5" />}{value === 'polo' && <path d="m25 18 3 10 4-3 4 3 3-10" />}</>;
  else if (kind === 'bottom') shape = value === 'skirt' ? <><path d="M22 13h20l11 39H11z" fill={color} /><path d="M22 17h20M26 23l-5 25m11-25v26m6-26 5 25" /></> : <><path d="M19 13h26l-2 41H33l-1-26-1 26H21z" fill={color} /><path d="M20 18h24M32 18v10M24 24v23m16-23v23" /></>;
  else if (kind === 'glasses') shape = value === 'none' ? <><circle cx="32" cy="32" r="20"/><path d="m18 18 28 28"/></> : <><rect x="5" y="23" width="23" height="17" rx={value === 'round' ? 8 : 3}/><rect x="36" y="23" width="23" height="17" rx={value === 'round' ? 8 : 3}/><path d="M28 27q4-4 8 0M5 28 1 26m58 2 4-2"/></>;
  else if (kind === 'shoe') shape = <><path d="m14 21 16 3 6 11 15 5q8 3 6 12H9q-5-7 0-14z" fill={color} /><path d="M9 48h47M26 30l8-2m-5 7 9-2m-5 7 9-2" /></>;
  else if (kind === 'hat') shape = value === 'none' ? <><circle cx="32" cy="32" r="20" /><path d="m18 18 28 28" /></> : value === 'bucket' ? <><path d="M22 15h20l5 24H17zM17 36 9 48q23 9 46 0l-8-12z" fill={color} /><path d="M21 29h22" /></> : value === 'beret' ? <><path d="M12 32q-4-19 25-19 28 0 18 24L17 40z" fill={color} /><path d="M19 36h30M34 14l2-7" /></> : <><path d="M13 36q0-23 20-23t20 23zM30 35q19-4 29 8H30z" fill={color} /><path d="M33 15v17" /></>;
  else if (kind === 'hair') shape = value === 'bald' ? <><path d="M15 45V31a17 17 0 0 1 34 0v14" /><path d="M23 48h18" /></> : value === 'curly' ? <><path d="M15 43V27h34v16" fill={color} />{[17, 27, 38, 48].map((x, i) => <circle key={x} cx={x} cy={i === 0 || i === 3 ? 28 : 20} r="9" fill={color} />)}</> : <><path d={value === 'long' ? 'M14 51V28q0-18 18-18t18 18v23l-10-4V30l-8-10-8 10v17z' : value === 'bob' ? 'M14 46V28q0-18 18-18t18 18v18l-10-4V28l-8-7-8 7v14z' : value === 'buzz' ? 'M15 30q0-16 17-16t17 16l-8-3H23z' : 'M14 37V26q0-17 18-17t18 17v11l-7-6V24l-13-4-10 11v6z'} fill={color} />{value === 'ponytail' && <path d="M46 23q17-1 11 21l-5 10-5-19z" fill={color} />}{value === 'sidepart' && <path d="M35 12 25 25" />}</>;
  else shape = <><circle cx="32" cy="18" r="9" /><path d={value === 'female' ? 'M23 32q9-4 18 0l7 22H16z' : 'M22 32h20l4 22H18z'} fill={color} /><path d="M25 54v5m14-5v5M21 35l-8 13m30-13 8 13" /></>;
  return <svg viewBox="0 0 64 64" width="56" height="56" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{shape}</svg>;
}

export function Wardrobe({ avatar, onChange }: { avatar: Record<string, string>; onChange: (next: Record<string, string>) => void }) {
  const [index, setIndex] = useState(0);
  const [gender, setGender] = useState<'male' | 'female'>(() => characterFor(avatar.presetId||avatar.bodyStyle).gender);
  useEffect(()=>{setGender(characterFor(avatar.presetId||avatar.bodyStyle).gender)},[avatar.presetId,avatar.bodyStyle]);
  const id = useId();
  const category = CATEGORIES[index];
  const selectedPreset = characterFor(avatar.presetId||avatar.bodyStyle).id;
  const change = (key: AvatarOptionKey, value: string) => onChange({ ...avatar, [key]: value });
  const color = AVATAR_OPTIONS[category.color].find(option => option.value === avatar[category.color])?.color;
  const selectedLabel = AVATAR_OPTIONS[category.color].find(option => option.value === avatar[category.color])?.label;
  const applyPreset = (preset: CharacterPreset) => onChange({ ...avatar, bodyStyle: preset.gender, presetId:preset.id, hairStyle: preset.hairStyle, hairColor: preset.hairColor, skinTone: preset.skinTone });
  const swatches = category.color === 'shirtColor'
    ? ['lightgreen', 'white', 'red', 'gray', 'charcoal', 'blueviolet'].flatMap(value => AVATAR_OPTIONS.shirtColor.filter(option => option.value === value))
    : AVATAR_OPTIONS[category.color];
  return <section className="wardrobe" aria-label="ห้องแต่งตัว">
    <div className="wardrobe-tabs" role="tablist" aria-label="หมวดการแต่งตัว">
      {CATEGORIES.map((item, i) => <button key={item.label} id={`${id}-tab-${i}`} type="button" role="tab" aria-selected={index === i} aria-controls={`${id}-panel`} tabIndex={index === i ? 0 : -1} className={`wardrobe-tab${index === i ? ' active' : ''}`} onClick={() => setIndex(i)} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const next = (i + (event.key === 'ArrowRight' ? 1 : -1) + CATEGORIES.length) % CATEGORIES.length; setIndex(next); document.getElementById(`${id}-tab-${next}`)?.focus(); } }}><ItemIcon kind={item.icon} value={item.style ? avatar[item.style] : ''} /><span>{item.label}</span></button>)}
    </div>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${index}`} className="wardrobe-panel">
      <div className="wardrobe-panel-heading"><span className="eyebrow">WARDROBE / {category.short}</span><h3>{category.label}</h3></div>
      {category.style === 'bodyStyle' && <div className="character-catalogue">
        <div className="character-gender-tabs" aria-label="กลุ่มตัวละคร">
          {(['male', 'female'] as const).map(value => <button type="button" key={value} className={gender === value ? 'selected' : ''} aria-pressed={gender === value} onClick={() => setGender(value)}>{value === 'male' ? 'ชาย · 10 แบบ' : 'หญิง · 10 แบบ'}</button>)}
        </div>
        <p className="character-catalogue-hint">เลือกใบหน้าและทรงผมที่ชอบ ชุดที่แต่งไว้ยังอยู่เหมือนเดิม</p>
        <div className="character-card-grid" aria-label={`เลือกตัวละคร${gender === 'male' ? 'ชาย' : 'หญิง'}`}>
          {CHARACTERS.filter(preset => preset.gender === gender).map(preset => <button type="button" key={preset.id} className={`character-card${selectedPreset === preset.id ? ' selected' : ''}`} aria-label={`${preset.id} ${preset.label}${selectedPreset === preset.id ? ' เลือกแล้ว' : ''}`} aria-pressed={selectedPreset === preset.id} onClick={() => applyPreset(preset)}>
            <span className="character-card-portrait"><Avatar className="character-card-avatar" options={{ ...avatar, bodyStyle: preset.gender, presetId:preset.id, hairStyle: preset.hairStyle, hairColor: preset.hairColor, skinTone: preset.skinTone, hatStyle: 'none' }} motion={false} /></span>
            <span className="character-card-id">{preset.id}</span><span className="character-card-label">{preset.label}</span><span className="character-card-check" aria-hidden="true">{selectedPreset === preset.id ? '✓' : ''}</span>
          </button>)}
        </div>
      </div>}
      {category.style && category.style !== 'bodyStyle' && <div className="wardrobe-tiles" aria-label={`เลือก${category.label}`}>
        {AVATAR_OPTIONS[category.style].map(option => <button type="button" key={option.value} className={`wardrobe-tile${avatar[category.style!] === option.value ? ' selected' : ''}`} aria-pressed={avatar[category.style!] === option.value} onClick={() => change(category.style!, option.value)}><ItemIcon kind={category.icon} value={option.value} color={color} /><span>{option.label}</span><span className="wardrobe-tile-check" aria-hidden="true">{avatar[category.style!] === option.value ? '✓' : ''}</span></button>)}
      </div>}
      {!category.style && <div className="wardrobe-item-preview"><ItemIcon kind="shoe" color={color} /><span>เลือกสีรองเท้าที่ใช่</span></div>}
      {category.color !== 'glassesStyle' && <div className="wardrobe-color-heading"><h4>{category.colorLabel}</h4><span>{selectedLabel}</span></div>}
      {category.color !== 'glassesStyle' && <div className="wardrobe-swatches" aria-label={category.colorLabel}>
        {swatches.map(option => <button type="button" key={option.value} className={`swatch-button${avatar[category.color] === option.value ? ' selected' : ''}`} aria-label={`${category.colorLabel}: ${option.label}`} aria-pressed={avatar[category.color] === option.value} title={option.label} onClick={() => change(category.color, option.value)}><span className="swatch-color" style={{ backgroundColor: option.color }}><span aria-hidden="true">{avatar[category.color] === option.value ? '✓' : ''}</span></span><span className="swatch-label">{option.label}</span></button>)}
      </div>}
    </div>
    <div className="wardrobe-navigation"><button type="button" style={{ minHeight: 48 }} onClick={() => setIndex((index + CATEGORIES.length - 1) % CATEGORIES.length)} aria-label="หมวดก่อนหน้า">← ก่อนหน้า</button><span>{index + 1} / {CATEGORIES.length}</span><button type="button" style={{ minHeight: 48 }} onClick={() => setIndex((index + 1) % CATEGORIES.length)} aria-label="หมวดถัดไป">ถัดไป →</button></div>
  </section>;
}
