/** Pure geometry used by both CSS preview and PNG export. */
export const AVATAR_CANVAS_WIDTH=600;
export const AVATAR_CANVAS_HEIGHT=800;
export const AVATAR_MAX_LAYER_HEIGHT=0.65;

/** Resolve a positioned image rectangle while preserving its source aspect ratio. */
export function avatarLayerRect(sourceWidth,sourceHeight,position,canvasWidth=AVATAR_CANVAS_WIDTH,canvasHeight=AVATAR_CANVAS_HEIGHT){
 if(!Number.isFinite(sourceWidth)||!Number.isFinite(sourceHeight)||sourceWidth<=0||sourceHeight<=0)throw new RangeError('Invalid source PNG dimensions');
 if(!Number.isFinite(canvasWidth)||!Number.isFinite(canvasHeight)||canvasWidth<=0||canvasHeight<=0)throw new RangeError('Invalid avatar canvas size');
 const {x,y,scale}=position??{};
 if(![x,y,scale].every(v=>Number.isFinite(v)&&v>=0&&v<=100)||scale===0)throw new RangeError('Invalid avatar layer position');
 const desiredWidth=canvasWidth*scale/100;
 const ratio=Math.min(1,canvasHeight*AVATAR_MAX_LAYER_HEIGHT/(desiredWidth*sourceHeight/sourceWidth));
 const width=desiredWidth*ratio;
 const height=width*sourceHeight/sourceWidth;
 return {left:canvasWidth*x/100-width/2,top:canvasHeight*y/100-height/2,width,height};
}
