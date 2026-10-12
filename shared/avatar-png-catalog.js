/** Selected PNG parts from the reviewed candidate pack. These paths become active when uploaded into /public/avatar-parts. */
export const PNG_PARTS=Object.freeze({
 // No approved transparent body bases have been uploaded; keep this empty until reviewed.
 body: [],
 face: [
  {value:'male',label:'ใบหน้าชาย',src:'/avatar-parts/male.png',ready:true,aligned:false},
  {value:'female',label:'ใบหน้าหญิง',src:'/avatar-parts/female.png',ready:true,aligned:false}
 ],
 hair: [
  {value:'shoulder',label:'ผมครึ่งหัวน้ำตาล',src:'/avatar-parts/hair2.png',ready:true,aligned:false},
  {value:'ponytail',label:'ผมบลอนด์',src:'/avatar-parts/hair4.png',ready:true,aligned:false}
 ],
 top: [
  {value:'overshirt',label:'เสื้อคลุมสีเบจ',src:'/avatar-parts/clothing_male_beige_overshirt.png',ready:true,aligned:false},
  {value:'shirt',label:'เสื้อโบฟ้า',src:'/avatar-parts/clothing_female_blue_bow_blouse.png',ready:false,aligned:false},
  {value:'jacket',label:'คาร์ดิแกนสีครีม',src:'/avatar-parts/clothing_female_cream_cardigan.png',ready:false,aligned:false},
  {value:'polo',label:'เสื้อโบขาว',src:'/avatar-parts/clothing_female_white_bow_blouse.png',ready:false,aligned:false},
  {value:'tshirt',label:'แจ็กเก็ตยีนส์',src:'/avatar-parts/clothing_male_blue_denim_jacket.png',ready:false,aligned:false}
 ],
 bottom: [
  {value:'pants',label:'กางเกงชิโน',src:'/avatar-parts/clothing_male_beige_chinos.png',ready:true,aligned:false},
  {value:'pants-jeans',label:'กางเกงยีนส์',src:'/avatar-parts/clothing_male_blue_jeans.png',ready:false,aligned:false},
  {value:'skirt',label:'กระโปรงพลีตดำ',src:'/avatar-parts/clothing_female_black_pleated_skirt.png',ready:false,aligned:false}
 ],
 glasses: [
  {value:'round',label:'แว่นกลม',src:'/avatar-parts/glasses_round.png',ready:false,aligned:false},
  {value:'rectangle',label:'แว่นเหลี่ยม',src:'/avatar-parts/glasses_rectangle.png',ready:false,aligned:false},
  {value:'aviator',label:'แว่นนักบิน',src:'/avatar-parts/glasses_aviator.png',ready:false,aligned:false}
 ],
 shoes: [
  {value:'beige',label:'รองเท้าครีม',src:'/avatar-parts/shoes_female_beige_maryjanes.png',ready:false,aligned:false},
  {value:'boots',label:'รองเท้าบูต',src:'/avatar-parts/shoes_female_brown_ankle_boots.png',ready:false,aligned:false},
  {value:'sneakers',label:'รองเท้าผ้าใบขาว',src:'/avatar-parts/shoes_female_white_sneakers.png',ready:true,aligned:false}
 ]
});
/** Files may not be present in a branch until the audited binary assets are committed. */
export const PNG_ASSETS_DIRECTORY='public/avatar-parts';
