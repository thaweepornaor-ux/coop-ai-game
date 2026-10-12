export interface AvatarLayerPosition {x:number;y:number;scale:number}
export interface AvatarLayerRectangle {left:number;top:number;width:number;height:number}
export const AVATAR_CANVAS_WIDTH:number;
export const AVATAR_CANVAS_HEIGHT:number;
export const AVATAR_MAX_LAYER_HEIGHT:number;
export function avatarLayerRect(sourceWidth:number,sourceHeight:number,position:AvatarLayerPosition,canvasWidth?:number,canvasHeight?:number):AvatarLayerRectangle;
