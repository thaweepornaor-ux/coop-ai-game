import type {AvatarChoices} from './avatar.js';
import {PNG_PARTS} from './avatar-png-catalog.js';
import type {PngPart} from './avatar-png-catalog.js';
export interface PlayableAvatarLayer extends PngPart {
 category:'body'|'bottom'|'shoes'|'top'|'face'|'hair'|'glasses';
 position:{x:number;y:number;scale:number};
}
export interface PlayableAvatarStack {ready:boolean;issues:string[];layers:PlayableAvatarLayer[];}
export const AVATAR_DRAW_ORDER:readonly PlayableAvatarLayer['category'][];
export function playableAvatarLayers(choices:Partial<AvatarChoices>|Record<string,unknown>,catalog?:typeof PNG_PARTS):PlayableAvatarStack;
