import { LOGO_BASE64, LOGO_MIME } from '../../../server/logo-data';
let bytes: Uint8Array | undefined;
export function GET() {
  if (!bytes) {
    const decoded = atob(LOGO_BASE64);
    bytes = Uint8Array.from(decoded, char => char.charCodeAt(0));
  }
  return new Response(bytes.slice().buffer as ArrayBuffer, { headers: {
    'Content-Type': LOGO_MIME,
    'Cache-Control': 'public, max-age=31536000, immutable',
    'X-Content-Type-Options': 'nosniff'
  } });
}
