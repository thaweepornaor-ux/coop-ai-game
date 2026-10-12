import type { AvatarOptionKey } from './avatar.js';

export type Gender = 'male' | 'female';
export type AnimationName = 'idle' | 'wave' | 'celebrate';
export type NormalizedSelection = Record<AvatarOptionKey | 'presetId', string>;
export interface GeometryState {
  visibility: Record<string, boolean>;
  morphs: { mesh: string; target: string; value: number }[];
}
export interface GeometryBinding { kind: 'geometry'; choices: Record<string, GeometryState>; }
export interface ColorBinding { kind: 'color'; materials: string[]; choices: Record<string, string>; }
export interface BodyAsset {
  asset: { url: string; sha256: string; byteLength: number; rigRoot: string; scale: number; rotationY: number };
  camera: { position: [number, number, number]; target: [number, number, number]; fov: number; near: number; far: number };
  presets: Record<string, GeometryState>;
  wardrobe: Record<Exclude<AvatarOptionKey, 'bodyStyle'>, GeometryBinding | ColorBinding>;
  clips: Record<AnimationName, string>;
}
export interface ProductionManifest {
  schemaVersion: 1; revision: string; threeVersion: '0.180.0';
  evidence: Record<'exportValidation' | 'artReview' | 'browserReview', { accepted: boolean; reference: string }>;
  bodies: Record<Gender, BodyAsset>;
}
export const THREE_VERSION: '0.180.0';
export const PRODUCTION_RENDER_REVISION: string;
export const ANIMATION_NAMES: readonly AnimationName[];
export const GEOMETRY_FIELDS: readonly string[];
export const COLOR_FIELDS: readonly string[];
export function stableJson(value: unknown): string;
export function stateTargets(state: GeometryState): string[];
export class AssetCapabilityError extends Error { readonly issues: string[]; constructor(issues: string[]); }
export function validateProductionManifest(value: unknown, options?: { mode?: 'production' | 'staging' }): { ready: boolean; issues: string[] };
export function assertProductionManifest(value: unknown, options?: { mode?: 'production' | 'staging' }): ProductionManifest;
export function thumbnailKey(manifest: ProductionManifest, selection: NormalizedSelection): string;
