import type {AvatarLayerPosition} from './avatar-png-layout.js';
export type AvatarAssemblyCategory='bottom'|'shoes'|'top'|'face'|'hair';
export type AvatarAssemblyGender='male'|'female';
export interface AvatarAssemblySnapshot {
 version:1;
 gender:AvatarAssemblyGender;
 positions:Record<AvatarAssemblyCategory,AvatarLayerPosition>;
 selected:Record<AvatarAssemblyCategory,string>;
}
export const PNG_ASSEMBLY_CATEGORIES:readonly AvatarAssemblyCategory[];
export const PNG_ASSEMBLY_VERSION:1;
export function validateAssemblySnapshot(input:unknown):AvatarAssemblySnapshot;
