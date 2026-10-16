/** Legacy-safe wardrobe choices. Values are always selected from a whitelist. */
const optionList = (items) => Object.freeze(items.map((item) => Object.freeze(item)));
export const AVATAR_OPTIONS = Object.freeze({
  bodyStyle: optionList([{ value: 'male', label: 'ผู้ชาย' }, { value: 'female', label: 'ผู้หญิง' }]),
  skinTone: optionList([
    { value: 'fair', label: 'ผิวสว่าง', color: '#F4CEB5' },
    { value: 'warm', label: 'ผิวอบอุ่น', color: '#DFAC86' },
    { value: 'tan', label: 'ผิวแทน', color: '#BD825E' },
    { value: 'deep', label: 'ผิวเข้ม', color: '#83543C' },
  ]),
  hairStyle: optionList([
    { value: 'short', label: 'ผมสั้น' }, { value: 'sidepart', label: 'ผมแสกข้าง' },
    { value: 'bob', label: 'ผมบ๊อบ' }, { value: 'long', label: 'ผมยาว' },
    { value: 'ponytail', label: 'ผมหางม้า' }, { value: 'curly', label: 'ผมหยิก' },
    { value: 'wavy', label: 'ผมหยักศก' }, { value: 'swept', label: 'ผมปัดข้าง' }, { value: 'shoulder', label: 'ผมประบ่า' }, { value: 'pixie', label: 'ผมสั้นเท่' }, { value: 'bun', label: 'มวยต่ำ' }, { value: 'buzz', label: 'ผมเกรียน' }, { value: 'bald', label: 'ไม่มีผม' },
  ]),
  hairColor: optionList([
    { value: 'black', label: 'ดำ', color: '#27313A' },
    { value: 'brown', label: 'น้ำตาล', color: '#654532' },
    { value: 'chestnut', label: 'น้ำตาลแดง', color: '#9A5940' },
    { value: 'blonde', label: 'ทอง', color: '#C49A54' },
    { value: 'saltpepper', label: 'ดำแซมเทา', color: '#646570' },
    { value: 'silver', label: 'เทาเงิน', color: '#A7ABB6' },
  ]),
  shirtStyle: optionList([
    { value: 'tshirt', label: 'เสื้อยืด' }, { value: 'polo', label: 'เสื้อโปโล' },
    { value: 'shirt', label: 'เสื้อเชิ้ต' }, { value: 'jacket', label: 'เสื้อแจ็กเก็ต' },
  ]),
  shirtColor: optionList([
    { value: 'lightgreen', label: 'เขียวอ่อน', color: '#A7CE98' },
    { value: 'red', label: 'แดง', color: '#C74745' },
    { value: 'gray', label: 'เทา', color: '#93999F' },
    { value: 'charcoal', label: 'ดำถ่าน', color: '#30343B' },
    { value: 'blueviolet', label: 'น้ำเงินอมม่วง', color: '#545994' },
    { value: 'indigo', label: 'คราม', color: '#5767C4' },
    { value: 'sky', label: 'ฟ้า', color: '#5CADD0' },
    { value: 'teal', label: 'เขียวทะเล', color: '#409E91' },
    { value: 'coral', label: 'ส้มปะการัง', color: '#E58272' },
    { value: 'gold', label: 'เหลือง', color: '#D9AA46' },
    { value: 'purple', label: 'ม่วง', color: '#9675BD' },
    { value: 'slate', label: 'เทา', color: '#6D8393' },
    { value: 'white', label: 'ขาว', color: '#F2F3EE' },
  ]),
  bottomStyle: optionList([{ value: 'pants', label: 'กางเกง' }, { value: 'skirt', label: 'กระโปรง' }]),
  bottomColor: optionList([
    { value: 'gray', label: 'เทา', color: '#93999F' },
    { value: 'navy', label: 'กรมท่า', color: '#37475E' },
    { value: 'denim', label: 'ยีนส์', color: '#507E9E' },
    { value: 'sand', label: 'เบจ', color: '#B6A17E' },
    { value: 'olive', label: 'เขียวมะกอก', color: '#76876B' },
    { value: 'charcoal', label: 'เทาเข้ม', color: '#535C66' },
  ]),
  shoeColor: optionList([
    { value: 'white', label: 'ขาว', color: '#F2F3EE' },
    { value: 'navy', label: 'กรมท่า', color: '#37475E' },
    { value: 'brown', label: 'น้ำตาล', color: '#895B42' },
    { value: 'black', label: 'ดำ', color: '#303943' },
    { value: 'coral', label: 'ส้มปะการัง', color: '#E58272' },
  ]),
  glassesStyle: optionList([{ value: 'none', label: 'ไม่ใส่แว่น' }, { value: 'round', label: 'แว่นทรงกลม' }, { value: 'rectangle', label: 'แว่นทรงเหลี่ยม' }, { value: 'aviator', label: 'แว่นทรงนักบิน' }]),
  hatStyle: optionList([
    { value: 'none', label: 'ไม่ใส่หมวก' }, { value: 'cap', label: 'หมวกแก๊ป' },
    { value: 'bucket', label: 'หมวกบักเก็ต' }, { value: 'beret', label: 'หมวกเบเร่ต์' },
  ]),
  hatColor: optionList([
    { value: 'navy', label: 'กรมท่า', color: '#37475E' },
    { value: 'sky', label: 'ฟ้า', color: '#5CADD0' },
    { value: 'teal', label: 'เขียวทะเล', color: '#409E91' },
    { value: 'sand', label: 'เบจ', color: '#C8B38B' },
    { value: 'coral', label: 'ส้มปะการัง', color: '#E58272' },
    { value: 'purple', label: 'ม่วง', color: '#9675BD' },
  ]),
});
const DEFAULTS = Object.freeze({
  bodyStyle: 'male', skinTone: 'warm', hairStyle: 'sidepart', hairColor: 'black',
  shirtStyle: 'polo', shirtColor: 'indigo', bottomStyle: 'pants',
  bottomColor: 'navy', shoeColor: 'white', glassesStyle: 'none', hatStyle: 'none', hatColor: 'navy',
});
const SKIN_SHADOWS = Object.freeze({ fair: '#DDAE92', warm: '#C38B68', tan: '#9E6548', deep: '#653D2D' });
const select = (input, key) => AVATAR_OPTIONS[key].find((item) => item.value === input[key])
  || AVATAR_OPTIONS[key].find((item) => item.value === DEFAULTS[key]);
const shade = (hex, ratio = 0.83) => '#' + [1, 3, 5].map((start) =>
  Math.round(parseInt(hex.slice(start, start + 2), 16) * ratio).toString(16).padStart(2, '0')).join('');

function backHair(style, color) {
  if (style === 'shoulder' || style === 'wavy') return `<path d="M52 60Q48 28 80 28Q111 28 108 60L113 111Q97 116 80 104Q63 116 47 111Z" fill="${color}"/><path d="M50 86Q57 82 50 97M110 86Q103 82 110 97" stroke="${shade(color)}" stroke-width="3" fill="none"/>`;
  if (style === 'bun') return `<ellipse cx="80" cy="92" rx="15" ry="12" fill="${color}"/><path d="M70 92Q80 102 90 92" stroke="${shade(color)}" stroke-width="2" fill="none"/>`;
  if (style === 'long') return `<path d="M53 56C49 26 111 24 108 57L112 109Q95 118 80 102Q65 118 48 109Z" fill="${color}"/><path d="M53 71L51 103M106 70L109 104" stroke="${shade(color)}" stroke-width="3" stroke-linecap="round"/>`;
  if (style === 'bob') return `<path d="M52 57C48 22 112 23 108 57L110 87Q100 102 80 91Q60 102 50 87Z" fill="${color}"/>`;
  if (style === 'ponytail') return `<path d="M100 49Q128 39 122 69Q117 84 125 101Q104 99 106 76L97 63Z" fill="${color}"/><path d="M111 58Q121 65 115 85" fill="none" stroke="${shade(color)}" stroke-width="3" stroke-linecap="round"/>`;
  if (style === 'curly') return `<g fill="${color}"><circle cx="57" cy="49" r="11"/><circle cx="55" cy="63" r="10"/><circle cx="59" cy="77" r="9"/><circle cx="103" cy="49" r="11"/><circle cx="105" cy="63" r="10"/><circle cx="101" cy="77" r="9"/></g>`;
  return '';
}
function frontHair(style, color) {
  // Every named preset should have its own visibly distinct silhouette.
  // Previously these aliases hid the wavy, swept, shoulder, pixie and bun assets.
  const dark = shade(color);
  switch (style) {
    case 'wavy': return `<path d="M52 65L53 45Q56 26 80 29Q107 26 108 48L107 67L99 61L97 46Q88 56 81 43Q70 57 61 54L60 66Z" fill="${color}"/><path d="M61 43Q72 33 81 38M87 36Q98 38 101 45" stroke="${dark}" stroke-width="2" fill="none"/>`;
    case 'shoulder': return `<path d="M54 74L53 46Q55 28 78 30Q104 27 107 46L108 79L101 76L98 47Q89 54 80 40Q67 52 62 54L60 76Z" fill="${color}"/><path d="M63 42Q79 30 97 41M53 65Q56 77 60 79M107 66Q105 78 102 80" stroke="${dark}" stroke-width="2" fill="none"/>`;
    case 'pixie': return `<path d="M55 58Q48 43 61 35Q78 22 96 32Q111 39 103 58L99 50L94 45Q84 49 74 41Q67 52 59 53Z" fill="${color}"/><path d="M65 37Q76 30 84 34" stroke="${dark}" stroke-width="2" fill="none"/>`;
    case 'swept': return `<path d="M55 61L54 43Q61 25 84 29Q104 28 107 45L103 61L99 54Q92 45 83 40Q72 57 58 59Z" fill="${color}"/><path d="M84 36Q73 45 60 49" stroke="${dark}" stroke-width="2" fill="none"/>`;
    case 'bun': return `<path d="M55 61L54 46Q58 27 81 28Q104 28 106 47L104 61L99 56L98 45Q80 50 62 44L61 61Z" fill="${color}"/><path d="M66 35Q80 31 97 39" stroke="${dark}" stroke-width="2" fill="none"/>`;
    case 'short': return `<path d="M56 60L55 47Q57 27 79 31Q98 25 105 44L104 59L99 51Q94 48 93 42Q77 50 63 45L61 59Z" fill="${color}"/><path d="M65 37Q78 32 91 36" fill="none" stroke="${dark}" stroke-width="2" stroke-linecap="round"/>`;
    case 'sidepart': return `<path d="M55 59L55 44Q58 27 79 31Q104 26 106 47L104 60L99 56L98 44Q89 48 74 45Q65 54 60 55L60 61Z" fill="${color}"/><path d="M75 33Q71 40 61 47M78 34Q90 33 99 40" fill="none" stroke="${dark}" stroke-width="2" stroke-linecap="round"/>`;
    case 'bob': return `<path d="M53 65L53 46Q57 28 80 30Q104 28 108 47L107 70L100 66L98 48Q86 54 77 45Q68 55 62 50L61 68Z" fill="${color}"/><path d="M61 40Q69 35 78 35" fill="none" stroke="${dark}" stroke-width="2" stroke-linecap="round"/>`;
    case 'long': return `<path d="M53 66L54 45Q58 29 79 31Q102 26 108 47L107 70L100 65L98 46Q86 48 80 39Q70 50 61 54L61 70Z" fill="${color}"/><path d="M80 34Q69 37 59 48" fill="none" stroke="${dark}" stroke-width="2" stroke-linecap="round"/>`;
    case 'ponytail': return `<path d="M55 59L55 45Q58 29 81 30Q102 29 105 47L104 60L99 56L97 44Q80 52 63 44L61 59Z" fill="${color}"/><path d="M65 38Q82 31 96 38" fill="none" stroke="${dark}" stroke-width="2" stroke-linecap="round"/><path d="M105 52L113 53" stroke="#E6BC69" stroke-width="5" stroke-linecap="round"/>`;
    case 'curly': return `<g fill="${color}"><circle cx="59" cy="44" r="10"/><circle cx="68" cy="35" r="10"/><circle cx="80" cy="33" r="11"/><circle cx="92" cy="35" r="10"/><circle cx="101" cy="44" r="10"/><circle cx="64" cy="48" r="7"/><circle cx="95" cy="49" r="7"/></g><path d="M68 31Q72 29 75 32M84 29Q88 27 91 31" fill="none" stroke="${dark}" stroke-width="2" stroke-linecap="round"/>`;
    case 'buzz': return `<path d="M56 51Q53 31 80 31Q107 31 104 51L99 48Q81 40 61 48Z" fill="${color}"/><path d="M62 40L63 41M71 36L72 37M81 35L82 36M91 36L92 37M98 40L99 41" stroke="${dark}" stroke-width="2" stroke-linecap="round"/>`;
    default: return '';
  }
}
function eyewear(style) {
 if(style==='round')return '<g fill="none" stroke="#30343B" stroke-width="2.5"><circle cx="69" cy="63" r="7"/><circle cx="91" cy="63" r="7"/><path d="M76 62Q80 59 84 62M62 60L56 58M98 60L104 58"/></g>';
 if(style==='rectangle')return '<g fill="none" stroke="#30343B" stroke-width="2.5"><rect x="61" y="57" width="16" height="12" rx="3"/><rect x="83" y="57" width="16" height="12" rx="3"/><path d="M77 61Q80 59 83 61M61 60L56 58M99 60L104 58"/></g>';
 if(style==='aviator')return '<g fill="none" stroke="#947748" stroke-width="2"><path d="M61 58Q69 55 77 58L76 66Q69 75 62 67Z"/><path d="M83 58Q91 55 99 58L98 67Q91 75 84 66Z"/><path d="M77 60Q80 58 83 60M61 60L56 57M99 60L104 57"/></g>';
 return '';
}
function hat(style, color) {
  const dark = shade(color);
  if (style === 'cap') return `<path d="M54 44Q54 22 80 22Q103 22 106 44Z" fill="${color}"/><path d="M80 23L80 39M60 41Q80 37 101 41" fill="none" stroke="${dark}" stroke-width="2"/><path d="M76 41Q99 35 121 43Q123 47 114 48L78 47Z" fill="${dark}"/><circle cx="80" cy="22" r="3" fill="${dark}"/>`;
  if (style === 'bucket') return `<path d="M60 24Q80 20 100 24L105 43L55 43Z" fill="${color}"/><path d="M58 35Q80 39 102 35" fill="none" stroke="${dark}" stroke-width="3"/><path d="M55 40L47 52Q80 61 113 52L105 40Q80 45 55 40Z" fill="${color}"/><path d="M48 52Q80 59 112 52" fill="none" stroke="${dark}" stroke-width="2"/>`;
  if (style === 'beret') return `<path d="M51 39Q45 28 66 23Q90 17 105 27Q118 38 102 45L58 45Z" fill="${color}"/><path d="M59 42Q79 39 102 43L101 48L59 47Z" fill="${dark}"/><path d="M81 22L83 17" stroke="${dark}" stroke-width="4" stroke-linecap="round"/>`;
  return '';
}
function shirtDetail(style, color) {
  const dark = shade(color);
  const neckline = `<path d="M68 94Q80 105 92 94" fill="none" stroke="${dark}" stroke-width="3" stroke-linecap="round"/>`;
  if (style === 'tshirt') return `${neckline}<path d="M91 114H99V123Q95 126 91 123Z" fill="${dark}" opacity=".5"/>`;
  if (style === 'polo') return `<path d="M68 94L79 99L73 107L64 97ZM92 94L81 99L87 107L96 97Z" fill="${dark}"/><path d="M80 100V116" stroke="${dark}" stroke-width="3"/><circle cx="80" cy="108" r="1.1" fill="#F7F5EC"/><circle cx="80" cy="114" r="1.1" fill="#F7F5EC"/><path d="M90 115H98" stroke="${dark}" stroke-width="2" stroke-linecap="round"/>`;
  if (style === 'shirt') return `<path d="M68 93L80 100L73 109L63 97ZM92 94L80 100L87 109L97 97Z" fill="${dark}"/><path d="M80 101V147" stroke="${dark}" stroke-width="2"/><g fill="#F7F5EC"><circle cx="81" cy="112" r="1.2"/><circle cx="81" cy="123" r="1.2"/><circle cx="81" cy="134" r="1.2"/></g><path d="M90 115H99V125Q95 128 90 125Z" fill="none" stroke="${dark}" stroke-width="1.5"/>`;
  return `<path d="M69 94L80 100L91 94L87 147H73Z" fill="#F4F0E7"/><path d="M68 94L79 102L71 113L65 103ZM92 94L81 102L89 113L95 103Z" fill="${dark}"/><path d="M80 104V148" stroke="${dark}" stroke-width="2"/><path d="M61 131L71 129M89 129L99 131" stroke="${dark}" stroke-width="2.5" stroke-linecap="round"/><rect x="79" y="139" width="3" height="5" rx="1" fill="#D6C6A5"/>`;
}

export function renderAvatar(options = {}) {
  const input = options && typeof options === 'object' ? options : {};
  const selected = Object.fromEntries(Object.keys(AVATAR_OPTIONS).map((key) => [key, select(input, key)]));
  const skin = selected.skinTone.color;
  const skinShade = SKIN_SHADOWS[selected.skinTone.value];
  const hairColor = selected.hairColor.color;
  const shirtColor = selected.shirtColor.color;
  const bottomColor = selected.bottomColor.color;
  const shoeColor = selected.shoeColor.color;
  const female = selected.bodyStyle.value === 'female';
  // Face geometry is derived from the approved 20 preset IDs, never arbitrary markup.
  const match = typeof input.presetId === 'string' ? /^(M|F)(0[1-9]|10)$/.exec(input.presetId) : null;
  const faceIndex = match && (match[1] === (female ? 'F' : 'M')) ? Number(match[2]) - 1 : 0;
  const faceWidth = [23,25,21,26,24,21.5,26,24.5,26.5,22.5][faceIndex];
  const faceLength = [29,27,32,28,30,28.5,27.5,31,29.5,31.5][faceIndex];
  const eyeOffset = [11,12,10.5,12.5,11.5,10,13,11,12,10.5][faceIndex];
  const eyeY = [63,64,62.5,63,63.5,62.5,64,63,64,62.5][faceIndex];
  const eyeWidth = [2.1,2,2.4,1.95,2.2,2.3,2,2.15,1.9,2.05][faceIndex];
  const noseTip = [71,70,73,72,71.5,70.5,72,73.5,72.5,74][faceIndex];
  const smileDepth = [6,4,5,7,6.5,4.5,5.5,7.5,4.5,6][faceIndex];
  // Subtle per-preset depth provides dimension without changing the chosen skin or hair.
  const cheekWidth = [4.8,5.1,4.4,5.3,4.9,4.5,5.2,4.7,5.0,4.6][faceIndex];
  const browLift = [0,1,-.5,.7,-.5,1,-1,.5,0,-.3][faceIndex];

  const shirtPath = female
    ? 'M68 94Q80 99 92 94L104 99L99 111L98 126L102 145Q80 152 58 145L62 126L61 111L56 99Z'
    : 'M66 94Q80 99 94 94L107 99L102 111L104 146Q80 152 56 146L58 111L53 99Z';
  const materialPrefix = typeof input.materialPrefix === 'string' && /^[a-zA-Z0-9_-]{1,72}$/.test(input.materialPrefix) ? input.materialPrefix : 'avatar';
  const bottom = selected.bottomStyle.value === 'skirt'
    ? `<g fill="${skin}"><path d="M61 172H75L74 191H62Z"/><path d="M85 172H99L98 191H86Z"/></g><path d="M60 143Q80 149 100 143L111 178Q81 188 49 178Z" fill="url(#${materialPrefix}-pants-lit)"/><path d="M60 145Q80 151 100 145" fill="none" stroke="${shade(bottomColor)}" stroke-width="4"/><path d="M66 154L62 176M80 155V180M94 154L99 176" stroke="${shade(bottomColor)}" stroke-width="2" opacity=".5"/><path d="M50 178Q80 187 110 178" fill="none" stroke="${shade(bottomColor)}" stroke-width="2"/>`
    : `<path d="M57 143Q80 149 103 143L101 187Q94 191 84 187L82 162H78L76 187Q68 191 59 187Z" fill="url(#${materialPrefix}-pants-lit)"/><path d="M58 145Q80 151 102 145" fill="none" stroke="${shade(bottomColor)}" stroke-width="4"/><path d="M80 151V161M64 157L65 180M96 157L95 180" stroke="${shade(bottomColor)}" stroke-width="2" stroke-linecap="round"/><path d="M59 185Q68 189 77 185M84 185Q93 189 101 185" fill="none" stroke="${shade(bottomColor)}" stroke-width="3"/>`;
  // A pose is a rendering-only choice: it never changes the persisted outfit.
  const pose = ['wave','celebrate','think','confident'].includes(input.pose) ? input.pose : 'stand';
  // Expressions belong to the preview pose, not the stored wardrobe.
  const expressionSmile = pose === 'celebrate' ? smileDepth + 3 : pose === 'wave' ? smileDepth + 1.3 : pose === 'think' ? Math.max(3,smileDepth - 2) : smileDepth;
  const poseEyes = pose === 'celebrate'
    ? `<g data-avatar-part="joyful-eyes" fill="none" stroke="#293443" stroke-width="2.3" stroke-linecap="round"><path d="M${80-eyeOffset-3} ${eyeY+1}Q${80-eyeOffset} ${eyeY-2} ${80-eyeOffset+3} ${eyeY+1}"/><path d="M${80+eyeOffset-3} ${eyeY+1}Q${80+eyeOffset} ${eyeY-2} ${80+eyeOffset+3} ${eyeY+1}"/></g>`
    : `<g fill="#293443"><ellipse cx="${80-eyeOffset}" cy="${eyeY}" rx="${eyeWidth}" ry="2.7"/><ellipse cx="${80+eyeOffset}" cy="${eyeY}" rx="${eyeWidth}" ry="2.7"/></g><g fill="#FFFFFF"><circle cx="${80-eyeOffset+.5}" cy="${eyeY-.9}" r=".7"/><circle cx="${80+eyeOffset+.5}" cy="${eyeY-.9}" r=".7"/></g>`;
  // Dedicated complete arm + visible palm/fingers geometry per pose.
  // Keep each silhouette attached to its shoulder. Hands are drawn at endpoints.
  // Resting palms share one anatomical silhouette. The right hand mirrors
  // the left rather than using a shorter, asymmetrical finger geometry.
  const relaxedPalmPath = 'M-5 -1Q-9 1 -9 7L-9 15Q-9 19 -7 19Q-5 19 -5 16L-5 20Q-5 23 -3 23Q-1 23 -1 20L-1 22Q-1 25 1 25Q3 25 3 21L3 19Q3 22 5 22Q7 22 7 19L7 13Q9 15 11 13Q13 11 10 8L6 2Q2 -3 -5 -1Z';
  const relaxedPalm = `<path data-avatar-part="relaxed-hand" d="${relaxedPalmPath}"/>`;
  const relaxedCreases = `<path d="M-5 10L-5 16M-1 11L-1 19M3 10L3 17" fill="none" stroke="${skinShade}" stroke-opacity=".48" stroke-width=".85" stroke-linecap="round"/>`;
  // Add a clipped palm-volume highlight to the shared resting hand. Both hands
  // use exactly the same contour, so the right-hand mirror also mirrors light.
  const relaxedPalmVolume = (side) => {
    const clipId = `${materialPrefix}-palm-${side}`;
    const palmPath = relaxedPalmPath;
    return `<clipPath id="${clipId}"><path d="${palmPath}"/></clipPath><g clip-path="url(#${clipId})"><path data-avatar-part="palm-volume" d="M-3 1Q1 -1 4 2Q6 5 5 9Q2 8 -2 10Q-4 6 -3 1Z" fill="#fff" fill-opacity=".12"/></g><path data-avatar-part="thumb-fold" d="M6 7Q8 10 9 11" fill="none" stroke="${skinShade}" stroke-width=".8" stroke-opacity=".32" stroke-linecap="round"/>`;
  };
  const leftRest = `<path data-avatar-part="left-forearm" d="M39 118Q37 128 38 139Q37 145 38 147Q42 151 47 147Q49 144 48 139Q49 131 49 124Z"/><g transform="translate(42 145)">${relaxedPalm}${relaxedPalmVolume('left')}${relaxedCreases}</g>`;
  const rightRest = `<path data-avatar-part="right-forearm" d="M121 118Q123 128 122 139Q123 145 122 147Q118 151 113 147Q111 144 112 139Q111 131 111 124Z"/><g data-avatar-part="mirrored-right-hand" transform="translate(118 145) scale(-1 1)">${relaxedPalm}${relaxedPalmVolume('right')}${relaxedCreases}</g>`;
  // Finger crease lines are deliberately subtle: they provide readable
  // articulation at small card sizes without making the palms look skeletal.
  // The paths are pose-local so raised and resting fingers are not reused.
  const fingerDetail = (kind) => {
    const crease = kind === 'open'
      ? 'M-6 -11L-4 -9M-2 -18L-1 -14M3 -18L4 -14M8 -15L7 -11'
      : kind === 'cheer'
      ? 'M-4 -10L-2 -8M0 -14L1 -11M5 -13L6 -10'
      : 'M-3 9L-3 13M1 9L1 14M5 8L5 12';
    return `<path data-avatar-part="finger-creases" d="${crease}" fill="none" stroke="${skinShade}" stroke-width=".8" stroke-opacity=".42" stroke-linecap="round"/>`;
  };
  // Separate palm from forearm with an anatomical wrist crease. It is
  // intentionally short and translucent so the hand remains one silhouette.
  const wristDetail = (kind) => {
    const contour = kind === 'wave' ? 'M-4 3Q0 5 4 3' : 'M-4 2Q0 4 4 2';
    return `<path data-avatar-part="wrist-crease" d="${contour}" fill="none" stroke="${skinShade}" stroke-width=".9" stroke-opacity=".34" stroke-linecap="round"/>`;
  };
  // Shading stays inside the broad center of a raised palm; pose-local creases
  // describe the thumb fold without drawing a new disconnected hand layer.
  const raisedPalmDepth = (kind) => {
    const highlight = kind === 'wave' ? 'M-4 -3Q0 -7 5 -4Q9 0 5 4Q0 6 -3 3Z' : 'M-4 -3Q0 -6 4 -4Q7 -1 5 3Q1 5 -3 3Z';
    const thumb = kind === 'wave' ? 'M-7 -8Q-5 -6 -4 -3' : 'M-5 -8Q-3 -6 -3 -3';
    return `<path data-avatar-part="raised-palm-depth" d="${highlight}" fill="#fff" fill-opacity=".12"/><path data-avatar-part="raised-thumb-fold" d="${thumb}" fill="none" stroke="${skinShade}" stroke-width=".8" stroke-opacity=".35" stroke-linecap="round"/>`;
  };
  const waveArm = `<path data-avatar-part="left-forearm" d="M30 93Q27 83 24 73Q23 68 27 67Q31 66 34 73Q37 88 39 104Z"/><g transform="translate(27 68) rotate(-15)"><g data-avatar-part="wave-palm-assembly" transform="scale(1.12)"><path data-avatar-part="open-hand" d="M-5 2Q-9 -1 -12 -7Q-13 -10 -10 -11Q-8 -12 -6 -8L-5 -10L-8 -19Q-9 -22 -6 -23Q-3 -23 -2 -19L-1 -11L-3 -23Q-3 -26 0 -26Q3 -26 3 -22L4 -11L5 -22Q5 -25 8 -24Q10 -23 9 -20L8 -10L10 -17Q11 -20 13 -18Q15 -16 13 -12L10 -1Q9 6 2 8Q-4 8 -5 2Z"/><path d="M-4 1Q1 4 6 0" fill="none" stroke="${skinShade}" stroke-width="1.1" stroke-opacity=".44" stroke-linecap="round"/>${raisedPalmDepth('wave')}${fingerDetail('open')}${wristDetail('wave')}</g></g>`;
  // Use the same clearly separated five-digit silhouette on both raised hands.
  // The mirrored hand is transformed as a unit, so finger direction, thumb
  // position and palm lighting stay symmetric without detached finger pieces.
  const celebrationPalm = `<g data-avatar-part="celebration-palm" transform="scale(.8)"><path data-avatar-part="open-hand" d="M-5 2Q-9 -1 -12 -7Q-13 -10 -10 -11Q-8 -12 -6 -8L-5 -10L-8 -19Q-9 -22 -6 -23Q-3 -23 -2 -19L-1 -11L-3 -23Q-3 -26 0 -26Q3 -26 3 -22L4 -11L5 -22Q5 -25 8 -24Q10 -23 9 -20L8 -10L10 -17Q11 -20 13 -18Q15 -16 13 -12L10 -1Q9 6 2 8Q-4 8 -5 2Z"/>${raisedPalmDepth('cheer')}${fingerDetail('open')}${wristDetail('cheer')}</g>`;
  const cheerLeft = `<path data-avatar-part="left-forearm" d="M32 88Q29 76 27 65Q26 59 31 58Q36 57 38 64Q37 84 38 102Z"/><g transform="translate(31 58)">${celebrationPalm}</g>`;
  const cheerRight = `<path data-avatar-part="right-forearm" d="M128 88Q131 76 133 65Q134 59 129 58Q124 57 122 64Q123 84 122 102Z"/><g data-avatar-part="mirrored-right-hand" transform="translate(129 58) scale(-1 1)">${celebrationPalm}</g>`;
  // Keep the relaxed left arm behind the shirt while only the raised right
  // forearm/hand crosses in front during thinking. Moving both arms to front
  // caused the left wrist and fingers to float over the torso hem.
  const thinkingRight = `<path data-avatar-part="right-forearm" d="M120 118Q125 129 117 136Q112 140 106 134L90 99Q86 93 92 89Q98 87 101 93L115 123L109 124Z"/><g transform="translate(93 86)"><path data-avatar-part="thinking-hand" d="M-6 2Q-8 -1 -6 -6L-4 -12Q-3 -16 0 -15Q3 -14 2 -10L1 -4L4 -12Q6 -15 9 -13Q11 -11 9 -7L8 2Q7 8 1 9Q-4 8 -6 2Z"/><path data-avatar-part="thinking-finger-joints" d="M-1 -4L1 0M2 -9Q4 -7 4 -4M-3 -8Q-2 -5 -3 -2" fill="none" stroke="${skinShade}" stroke-width=".85" stroke-opacity=".38" stroke-linecap="round"/><path data-avatar-part="thinking-palm-volume" d="M-4 0Q-4 -3 -1 -5L4 -4Q6 0 4 5Q0 7 -3 4Z" fill="#fff" fill-opacity=".09"/><path data-avatar-part="thinking-thumb-joint" d="M-5 -2Q-3 -1 -2 1" fill="none" stroke="${skinShade}" stroke-opacity=".35" stroke-width=".75" stroke-linecap="round"/><path data-avatar-part="thinking-finger-highlight" d="M1 -10Q2 -12 4 -11" fill="none" stroke="#fff" stroke-opacity=".2" stroke-width=".7" stroke-linecap="round"/></g>`;
  // Confident fists must be visible in FRONT of the waist. Their two
  // forearms stay behind the shirt to preserve the shoulder and sleeve joins.
  const confidentForearms = `<path data-avatar-part="left-forearm" d="M40 118Q38 132 44 139Q50 144 60 138L60 136Q57 133 55 133L49 130L50 124Z"/><path data-avatar-part="right-forearm" d="M120 118Q122 132 116 139Q110 144 100 138L100 136Q103 133 105 133L111 130L110 124Z"/>`;
  const confidentFistArt = `<path data-avatar-part="closed-hand" d="M54 135Q53 130 57 129Q61 127 65 130Q69 132 69 136Q69 140 64 141L58 141Q54 140 54 135Z"/><path data-avatar-part="fist-knuckles" d="M57 134Q58 133 59 134M60 133Q61 132 62 133M63 133Q64 133 65 134" fill="none" stroke="${skinShade}" stroke-width="1.2" stroke-linecap="round"/><path data-avatar-part="fist-volume" d="M57 134Q58 132 61 132Q64 132 65 134Q64 137 60 137Q57 137 57 134Z" fill="#fff" fill-opacity=".09"/><path data-avatar-part="fist-thumb-fold" d="M57 135Q58 133 61 134" fill="none" stroke="${skinShade}" stroke-opacity=".32" stroke-width=".72" stroke-linecap="round"/><path data-avatar-part="fist-knuckle-light" d="M58 133Q61 132 64 133" fill="none" stroke="#fff" stroke-opacity=".2" stroke-width=".8" stroke-linecap="round"/>`;
  const confidentFists = `<g data-avatar-part="left-confident-hand" transform="translate(60 135) scale(1.16) translate(-60 -135)">${confidentFistArt}</g><g data-avatar-part="right-confident-hand" transform="translate(160 0) scale(-1 1)"><g transform="translate(60 135) scale(1.16) translate(-60 -135)">${confidentFistArt}</g></g>`;
  const armShape = pose === 'wave' ? waveArm+rightRest
    : pose === 'celebrate' ? cheerLeft+cheerRight
    : pose === 'think' ? leftRest+thinkingRight
    : pose === 'confident' ? confidentForearms
    : leftRest+rightRest;
  // Each pose has its own closed fabric sleeve silhouettes, rather than
  // fixed-width strokes laid over skin. Shoulder ends overlap the shirt body;
  // cuff ends terminate at the actual forearm direction of that pose.
  const sleevesByPose = {
    stand: [
      'M53 99Q47 99 43 106Q40 112 39 118Q43 122 49 124Q53 114 58 108Q57 102 53 99Z',
      'M107 99Q113 99 117 106Q120 112 121 118Q117 122 111 124Q107 114 102 108Q103 102 107 99Z',
    ],
    wave: [
      'M54 99Q47 98 41 92L37 86Q33 87 30 93Q34 99 39 104Q45 113 55 114L59 108Q58 102 54 99Z',
      'M107 99Q113 99 117 106Q120 112 121 118Q117 122 111 124Q107 114 102 108Q103 102 107 99Z',
    ],
    celebrate: [
      'M54 99Q49 95 45 88L41 82Q35 83 32 88Q35 95 38 102Q44 113 55 114L59 107Q58 102 54 99Z',
      'M106 99Q111 95 115 88L119 82Q125 83 128 88Q125 95 122 102Q116 113 105 114L101 107Q102 102 106 99Z',
    ],
    think: [
      'M53 99Q47 99 43 106Q40 112 39 118Q43 122 49 124Q53 114 58 108Q57 102 53 99Z',
      'M107 99Q114 99 117 107Q120 113 120 118Q116 122 109 124L102 110Q103 103 107 99Z',
    ],
    confident: [
      'M53 99Q46 100 43 107Q40 113 40 118Q44 122 50 124L57 110Q58 103 53 99Z',
      'M107 99Q114 100 117 107Q120 113 120 118Q116 122 110 124L103 110Q102 103 107 99Z',
    ],
  };
  const sleeves = sleevesByPose[pose];
  // The cuff follows each shoulder-to-forearm direction.  A soft fabric edge
  // reads as a rolled hem instead of a hard painted outline over the skin.
  const cuffsByPose = {
    stand:['M39 118Q43 122 49 124','M121 118Q117 122 111 124'],
    wave:['M30 93Q34 99 39 104','M121 118Q117 122 111 124'],
    celebrate:['M32 88Q35 95 38 102','M128 88Q125 95 122 102'],
    think:['M39 118Q43 122 49 124','M120 118Q116 122 109 124'],
    confident:['M40 118Q44 122 50 124','M120 118Q116 122 110 124'],
  };
  // Highlight only the raised fabric fold; skin remains visible underneath
  // and the cuff follows the actual exposed forearm for every pose.
  const foldsByPose = {
    stand:['M48 105Q45 110 44 114','M112 105Q115 110 116 114'],
    wave:['M50 102Q45 99 41 96','M112 105Q115 110 116 114'],
    celebrate:['M51 103Q46 98 43 93','M109 103Q114 98 117 93'],
    think:['M48 105Q45 110 44 114','M112 105Q115 110 116 114'],
    confident:['M48 105Q45 110 44 114','M112 105Q115 110 116 114']
  };
  // Build the shoulder-to-sleeve connection from the back forward: shoulder
  // fabric, join seam, moving sleeve, then its cuff. Caps drawn after sleeves
  // used to make a detached patch at the top of the raised arm.
  // Shoulder cloth follows the same movement as the actual pose sleeves.
  // Fixed shoulder patches created visible bulges when one or both arms were raised.
  const shoulderProfiles = {
    stand: [
      'M49 101Q53 97 57 99Q61 101 61 107L57 113Q52 110 49 105Z',
      'M111 101Q107 97 103 99Q99 101 99 107L103 113Q108 110 111 105Z'
    ],
    wave: [
      'M49 96Q52 96 55 99Q59 102 60 106L56 111Q49 107 45 101Z',
      'M111 101Q107 97 103 99Q99 101 99 107L103 113Q108 110 111 105Z'
    ],
    celebrate: [
      'M48 94Q52 95 55 99Q59 102 60 107L56 111Q49 105 45 99Z',
      'M112 94Q108 95 105 99Q101 102 100 107L104 111Q111 105 115 99Z'
    ],
    think: [
      'M49 101Q53 97 57 99Q61 101 61 107L57 113Q52 110 49 105Z',
      'M111 99Q107 97 104 99Q100 101 99 108L104 112Q109 109 113 104Z'
    ],
    confident: [
      'M49 101Q53 98 57 99Q61 102 60 108L56 113Q51 110 49 105Z',
      'M111 101Q107 98 103 99Q99 102 100 108L104 113Q109 110 111 105Z'
    ]
  };
  const shoulderCaps = '<g data-avatar-part="shoulder-caps">' +
    shoulderProfiles[pose].map((d,side)=>`<path data-avatar-part="${side===0?'left':'right'}-shoulder-cap" d="${d}"/>`).join('') + '</g>';
  const shoulderJoin = (side) => {
    const raised = pose==='celebrate'||(pose==='wave'&&side===0);
    const bent = pose==='think'&&side===1;
    const d = side===0
      ? raised ? 'M52 98Q56 99 59 105' : 'M54 99Q58 100 60 105'
      : raised ? 'M108 98Q104 99 101 105' : bent ? 'M107 99Q103 100 101 106' : 'M106 99Q102 100 100 105';
    return `<path data-avatar-part="shoulder-join-${side===0?'left':'right'}" d="${d}" fill="none" stroke="${shirtColor}" stroke-width="2.4" stroke-linecap="round"/>`;
  };
  // Fabric geometry is shared; outfit style changes only its finishing treatment.
  const sleeveFinish = selected.shirtStyle.value === 'jacket'
    ? {edgeWidth:2.4,edgeOpacity:.65,foldOpacity:.13}
    : selected.shirtStyle.value === 'shirt'
    ? {edgeWidth:1.6,edgeOpacity:.54,foldOpacity:.24}
    : selected.shirtStyle.value === 'tshirt'
    ? {edgeWidth:1.15,edgeOpacity:.38,foldOpacity:.16}
    : {edgeWidth:1.45,edgeOpacity:.5,foldOpacity:.2};
  // Each sleeve's illumination is clipped to its own moving fabric polygon.
  // This prevents highlight strokes spilling into bare skin at the armpit or cuff.
  const sleeveOverlay = '<g data-avatar-part="pose-sleeves">' + sleeves.map((d, side) => {
    const direction = side===0?'left':'right';
    const clipId = materialPrefix+'-sleeve-'+direction;
    const raised = pose==='celebrate'||(pose==='wave'&&side===0);
    const fold = foldsByPose[pose][side];
    const volume = raised
      ? (side===0?'M31 89Q42 98 55 107':'M129 89Q118 98 105 107')
      : (side===0?'M42 109Q48 104 56 106':'M118 109Q112 104 104 106');
    const underarmSeam = raised
      ? (side===0?'M42 100Q48 108 54 110':'M118 100Q112 108 106 110')
      : (side===0?'M49 119Q54 112 57 108':'M111 119Q106 112 103 108');
    // Shoulder yoke is part of the same clipped sleeve polygon, not an
    // independent patch that can float above the shoulder in raised poses.
    const jacketYoke = selected.shirtStyle.value==='jacket'
      ? `<path data-avatar-part="jacket-shoulder-yoke" d="${raised
          ? (side===0?'M35 88Q44 92 55 103L53 109Q43 101 33 94Z':'M125 88Q116 92 105 103L107 109Q117 101 127 94Z')
          : (side===0?'M51 99Q44 103 41 114L47 118Q50 108 57 104Z':'M109 99Q116 103 119 114L113 118Q110 108 103 104Z')}" fill="${shade(shirtColor)}" fill-opacity=".18" stroke="${shade(shirtColor)}" stroke-opacity=".3" stroke-width=".55"/>`
      : '';
    const jacketStitch = selected.shirtStyle.value==='jacket'
      ? `<path data-avatar-part="jacket-sleeve-stitch" d="${underarmSeam}" fill="none" stroke="${shade(shirtColor)}" stroke-opacity=".46" stroke-width=".55" stroke-dasharray="1.6 1.15" stroke-linecap="round"/>`
      : '';
    return `<clipPath id="${clipId}"><path d="${d}"/></clipPath><path data-sleeve-side="${direction}" d="${d}" fill="url(#${materialPrefix}-shirt-lit)" stroke="${shade(shirtColor)}" stroke-opacity=".14" stroke-width=".6" stroke-linejoin="round"/><g data-avatar-part="sleeve-material-${direction}" clip-path="url(#${clipId})">${jacketYoke}<path data-avatar-part="sleeve-volume" d="${volume}" fill="none" stroke="#fff" stroke-opacity=".23" stroke-width="6" stroke-linecap="round"/><path data-avatar-part="sleeve-fold" d="${fold}" fill="none" stroke="#fff" stroke-opacity="${sleeveFinish.foldOpacity}" stroke-width="1.6" stroke-linecap="round"/><path data-avatar-part="sleeve-underarm-seam" d="${underarmSeam}" fill="none" stroke="${shade(shirtColor)}" stroke-opacity=".26" stroke-width="1.2" stroke-linecap="round"/>${jacketStitch}</g><path data-avatar-part="sleeve-cuff" d="${cuffsByPose[pose][side]}" fill="none" stroke="${shade(shirtColor)}" stroke-opacity="${sleeveFinish.edgeOpacity}" stroke-width="${sleeveFinish.edgeWidth}" stroke-linecap="round"/>`;
  }).join('') + '</g>';
  const shoes = `<g fill="${shoeColor}"><path d="M61 189L74 189L76 197Q75 203 61 203L52 203Q48 196 57 194Z"/><path d="M86 189L99 189L103 194Q112 196 108 203H98Q85 203 84 197Z"/></g><path d="M51 202H76M85 202H109" stroke="#D1D6D9" stroke-width="3" stroke-linecap="round"/><path d="M62 193L69 194M92 194L99 193" stroke="${shade(shoeColor)}" stroke-width="2" stroke-linecap="round"/>`;
  // Material-lighting pass for editable avatars. Each SVG owns its gradient IDs.
  // All fills still derive from the user's exact selected outfit palette.
  const materialDefs = `<defs>
    <linearGradient id="${materialPrefix}-skin-lit" x1="0%" y1="10%" x2="95%" y2="90%"><stop offset="0%" stop-color="${skin}"/><stop offset="38%" stop-color="${skin}"/><stop offset="100%" stop-color="${skinShade}"/></linearGradient>
    <linearGradient id="${materialPrefix}-shirt-lit" x1="0%" y1="0%" x2="100%" y2="40%"><stop offset="0%" stop-color="${shirtColor}"/><stop offset="24%" stop-color="${shirtColor}"/><stop offset="78%" stop-color="${shirtColor}"/><stop offset="100%" stop-color="${shade(shirtColor)}"/></linearGradient>
    <linearGradient id="${materialPrefix}-pants-lit" x1="0%" x2="100%" y1="0%" y2="30%"><stop offset="0%" stop-color="${shade(bottomColor)}"/><stop offset="33%" stop-color="${bottomColor}"/><stop offset="67%" stop-color="${bottomColor}"/><stop offset="100%" stop-color="${shade(bottomColor)}"/></linearGradient>
    <radialGradient id="${materialPrefix}-face-lit" cx="29%" cy="24%" r="85%"><stop offset="0%" stop-color="${skin}"/><stop offset="40%" stop-color="${skin}"/><stop offset="100%" stop-color="${skinShade}"/></radialGradient>
  </defs>`;
  // A thinking gesture crosses the chest: draw that forearm IN FRONT of
  // the torso, but keep relaxed and raised arms behind the torso as before.
  const armsBehindTorso = pose === 'think' ? leftRest : armShape;
  const armsInFrontOfTorso = pose === 'think' ? thinkingRight : pose === 'confident' ? confidentFists : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 220" data-avatar-pose="${pose}" width="160" height="220" role="img" aria-label="ตัวละครผู้เล่น" style="display:block;width:100%;height:100%;overflow:visible"><ellipse cx="80" cy="209" rx="37" ry="5" fill="#34445D" opacity=".16"/>${materialDefs}${backHair(selected.hairStyle.value, hairColor)}${bottom}${shoes}<g fill="url(#${materialPrefix}-skin-lit)">${armsBehindTorso}</g><rect x="72" y="81" width="16" height="20" rx="6" fill="${skin}"/><path d="M72 84Q80 91 88 84V91Q80 96 72 91Z" fill="${skinShade}"/><path data-avatar-part="shirt-torso" d="${shirtPath}" fill="url(#${materialPrefix}-shirt-lit)"/><path d="M61 139Q80 144 99 139" fill="none" stroke="${shade(shirtColor)}" stroke-width="2" opacity=".35"/><path data-avatar-part="shirt-volume" d="M62 115Q69 121 71 133M97 116Q91 124 91 136" fill="none" stroke="#fff" stroke-width="1.4" opacity=".22"/><path data-avatar-part="shirt-side-shading" d="M59 117Q62 130 60 142Q66 145 72 145M102 116Q98 130 101 142Q96 145 91 146" fill="none" stroke="${shade(shirtColor)}" stroke-opacity=".22" stroke-width="2.1" stroke-linecap="round"/>${shirtDetail(selected.shirtStyle.value, shirtColor)}<g fill="url(#${materialPrefix}-skin-lit)">${armsInFrontOfTorso}</g><g fill="url(#${materialPrefix}-shirt-lit)">${shoulderCaps}</g>${shoulderJoin(0)}${shoulderJoin(1)}${sleeveOverlay}<g fill="url(#${materialPrefix}-face-lit)"><ellipse cx="57" cy="63" rx="5" ry="7"/><ellipse cx="103" cy="63" rx="5" ry="7"/><ellipse cx="80" cy="61" rx="${faceWidth}" ry="${faceLength}"/></g><path d="M55 62Q59 59 60 65M105 62Q101 59 100 65" fill="none" stroke="${skinShade}" stroke-width="1.5" stroke-linecap="round"/><path d="M80 63L77 ${noseTip}Q80 ${noseTip+2} 83 ${noseTip}" fill="none" stroke="${skinShade}" stroke-width="1.8" stroke-linecap="round"/>${frontHair(selected.hairStyle.value, hairColor)}<path data-avatar-part="brows" d="M65 ${56+browLift}Q69 ${54+browLift} 73 ${56+browLift}M87 ${56+browLift}Q91 ${54+browLift} 95 ${56+browLift}" fill="none" stroke="${shade(hairColor)}" stroke-width="2" stroke-linecap="round"/>${poseEyes}<g data-avatar-part="face-cheeks" fill="#D57468" opacity=".22"><ellipse cx="64" cy="72" rx="${cheekWidth}" ry="2.7"/><ellipse cx="96" cy="72" rx="${cheekWidth}" ry="2.7"/></g><path data-avatar-part="face-chin-light" d="M70 83Q80 89 90 83" fill="none" stroke="#fff" stroke-width="1.3" stroke-opacity=".16" stroke-linecap="round"/><path d="M73 78Q80 ${78+expressionSmile} 87 78" fill="none" stroke="#854E43" stroke-width="2" stroke-linecap="round"/>${eyewear(selected.glassesStyle.value)}${hat(selected.hatStyle.value, selected.hatColor.color)}</svg>`;
}
