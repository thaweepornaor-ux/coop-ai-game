import type {CSSProperties} from 'react';
type Pose='welcome'|'scan'|'think'|'explain'|'celebrate';
/**
 * Original in-game robot identity. No synthetic NHK logo or changed employee
 * uniform: branded humans are sourced from the user's unchanged PNG artwork.
 * Each robot pose communicates a distinct game state, never replaces gameplay.
 */
export function GameMascot({pose,className='',style}:{pose:Pose;className?:string;style?:CSSProperties}){
 const cheering=pose==='celebrate',thinking=pose==='think',explaining=pose==='explain',scanning=pose==='scan';
 const armLeft=cheering?'M47 127 Q25 112 31 81':thinking?'M47 130 Q28 136 30 108':explaining?'M47 128 Q26 110 23 95':'M47 127 Q23 115 24 93';
 const armRight=cheering?'M150 127 Q173 100 167 73':thinking?'M150 130 Q165 104 147 84':explaining?'M150 128 Q184 113 187 86':scanning?'M150 127 Q181 111 183 92':'M150 127 Q177 111 169 81';
 return <svg className={'game-mascot '+className} style={style} viewBox="0 0 210 220" role="img" aria-label={pose==='welcome'?'มาสคอต AI โบกมือต้อนรับ':pose==='scan'?'มาสคอต AI ชี้วิธีสแกน':pose==='think'?'มาสคอต AI กำลังคิด':pose==='explain'?'มาสคอต AI ช่วยอธิบายเฉลย':'มาสคอต AI ฉลองผลการแข่งขัน'}>
  <defs><linearGradient id={'bot-'+pose} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ecfbff"/><stop offset=".48" stopColor="#9cdeef"/><stop offset="1" stopColor="#5a91c7"/></linearGradient><linearGradient id={'screen-'+pose} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#2c477a"/><stop offset="1" stopColor="#163161"/></linearGradient></defs>
  <ellipse cx="104" cy="207" rx="71" ry="9" fill="#6ce5ec" opacity=".26"/>
  <g stroke="#9beafa" strokeWidth="11" strokeLinecap="round" fill="none"><path d={armLeft}/><path d={armRight}/></g>
  <g fill="#effaff" stroke="#5bb3d5" strokeWidth="2.3"><circle cx={cheering?31:thinking?30:explaining?23:24} cy={cheering?81:thinking?108:explaining?95:93} r="10"/><circle cx={cheering?167:thinking?147:explaining?187:scanning?183:169} cy={cheering?73:thinking?84:explaining?86:scanning?92:81} r="10"/></g>
  <rect x="56" y="110" width="96" height="82" rx="33" fill={'url(#bot-'+pose+')'} stroke="#c1f3ff" strokeWidth="3"/>
  <rect x="85" y="174" width="38" height="8" rx="4" fill="#5aa8c6" opacity=".75"/>
  <rect x="43" y="39" width="122" height="105" rx="35" fill={'url(#bot-'+pose+')'} stroke="#e6ffff" strokeWidth="4"/>
  <path d="M103 39 V19" stroke="#a7f2ff" strokeWidth="6" strokeLinecap="round"/><circle cx="103" cy="15" r="9" fill="#ffda86" stroke="#ffebbd" strokeWidth="2"/>
  <rect x="56" y="56" width="96" height="68" rx="24" fill={'url(#screen-'+pose+')'} stroke="#6cd9e7" strokeWidth="3"/>
  {thinking?<><path d="M70 85 Q83 70 92 83 M114 83 Q125 70 139 85" fill="none" stroke="#9dfaf0" strokeWidth="5" strokeLinecap="round"/><circle cx="100" cy="104" r="5" fill="#9dfaf0"/></>:<><path d="M72 84 Q81 73 91 84 M114 84 Q126 73 136 84" stroke="#9dfaf0" strokeWidth="5" fill="none" strokeLinecap="round"/><path d={cheering?'M78 101 Q103 125 131 101':'M84 104 Q103 117 122 104'} fill="none" stroke="#b7ffff" strokeWidth="4" strokeLinecap="round"/></>}
  <circle cx="102" cy="152" r="16" fill="#37679a" stroke="#b9f1ff" strokeWidth="2"/><text x="102" y="158" textAnchor="middle" fontSize="16" fontWeight="900" fill="#ddffff">AI</text>
  {thinking&&<g transform="translate(150 12)"><path d="M12 0 C-9 0 -14 28 0 37 V48 H25 V37 C40 25 32 0 12 0Z" fill="#ffe1a2" stroke="#f0ba61" strokeWidth="3"/><path d="M7 55 H21" stroke="#fff0ba" strokeWidth="4" strokeLinecap="round"/></g>}
  {explaining&&<g transform="translate(155 10)"><rect x="0" y="0" rx="13" width="47" height="42" fill="#eaf8ff" stroke="#64bbcc" strokeWidth="2"/><path d="M11 22 L20 30 L35 13" fill="none" stroke="#339a85" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round"/></g>}
  {scanning&&<g transform="translate(161 2)"><rect x="0" y="0" rx="9" width="34" height="58" fill="#e6f7ff" stroke="#589fce" strokeWidth="3"/><rect x="5" y="8" width="24" height="34" rx="3" fill="#fff"/><path d="M10 15 H23 M10 21 H23 M10 27 H18 M10 32 H23" stroke="#3967a7" strokeWidth="2"/></g>}
  {cheering&&<g transform="translate(7 0)"><path d="M5 15 H40 V33 Q40 58 22 62 Q5 58 5 33Z" fill="#ffdca0" stroke="#e3b05a" strokeWidth="3"/><path d="M5 27 H-3 Q-4 46 13 49 M40 27 H48 Q49 46 33 49" fill="none" stroke="#ffdca0" strokeWidth="6"/><path d="M22 63 V74 M9 77 H35" stroke="#e3b05a" strokeWidth="6" strokeLinecap="round"/></g>}
  <g className="mascot-sparkles" fill="#a1f9ef"><circle cx="27" cy="47" r="4"/><circle cx="182" cy="155" r="3"/><path d="M176 24 l4 9 9 4 -9 4 -4 9 -4 -9 -9 -4 9 -4Z"/></g>
 </svg>;
}
export function StaffArtwork({className='',title='ภาพตัวละครต้นฉบับผู้ใช้'}:{className?:string;title?:string}){
 return <img className={'game-staff-art '+className} src="/art/nhk-staff-original.svg" alt={title} loading="lazy" decoding="async"/>;
}
