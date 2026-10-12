/** Selected PNG parts from the reviewed candidate pack. These paths become active when uploaded into /public/avatar-parts. */
export const PNG_PARTS=Object.freeze({
 face: [
  {value:'male',label:'ใบหน้าชาย',src:'/avatar-parts/male.png'},
  {value:'female',label:'ใบหน้าหญิง',src:'/avatar-parts/female.png'}
 ],
 hair: [
  {value:'halfup',label:'ผมครึ่งหัวน้ำตาล',src:'/avatar-parts/hair2.png'},
  {value:'blonde',label:'ผมบลอนด์',src:'/avatar-parts/hair4.png'}
 ],
 top: [
  {value:'bluebow',label:'เสื้อโบฟ้า',src:'/avatar-parts/clothing_female_blue_bow_blouse.png'},
  {value:'cream',label:'คาร์ดิแกนสีครีม',src:'/avatar-parts/clothing_female_cream_cardigan.png'},
  {value:'whitebow',label:'เสื้อโบขาว',src:'/avatar-parts/clothing_female_white_bow_blouse.png'},
  {value:'denim',label:'แจ็กเก็ตยีนส์',src:'/avatar-parts/clothing_male_blue_denim_jacket.png'}
 ],
 bottom: [
  {value:'chinos',label:'กางเกงชิโน',src:'/avatar-parts/clothing_male_beige_chinos.png'},
  {value:'jeans',label:'กางเกงยีนส์',src:'/avatar-parts/clothing_male_blue_jeans.png'},
  {value:'skirt',label:'กระโปรงพลีตดำ',src:'/avatar-parts/clothing_female_black_pleated_skirt.png'}
 ],
 shoes: [
  {value:'beige',label:'รองเท้าครีม',src:'/avatar-parts/shoes_female_beige_maryjanes.png'},
  {value:'boots',label:'รองเท้าบูต',src:'/avatar-parts/shoes_female_brown_ankle_boots.png'},
  {value:'sneakers',label:'รองเท้าผ้าใบขาว',src:'/avatar-parts/shoes_female_white_sneakers.png'}
 ]
});
/** Files may not be present in a branch until the audited binary assets are committed. */
export const PNG_ASSETS_DIRECTORY='public/avatar-parts';
