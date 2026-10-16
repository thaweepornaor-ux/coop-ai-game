// Gallery and hero share the exact same visible default pose.
// Deliberately render-only; never write pose into saved wardrobe state.
/** @typedef {'stand'|'wave'|'think'|'confident'|'celebrate'} AvatarPose */
const poseCycle=/** @type {const} */ (['wave','confident','think','stand','celebrate']);
/** @param {unknown} presetId @returns {AvatarPose} */
export function poseForAvatarPreset(presetId){
 const match=typeof presetId==='string'?/^[MF](0[1-9]|10)$/.exec(presetId):null;
 if(!match)return 'stand';
 return poseCycle[(Number(match[1])-1)%poseCycle.length];
}
