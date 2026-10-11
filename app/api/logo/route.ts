// Preserve the original cooperative logo as a static asset.
// This same-origin redirect avoids a multi-megabyte JavaScript base64 module.
export function GET() {
  return new Response(null, { status: 307, headers: {
    Location: '/logo.jpg',
    'Cache-Control': 'public, max-age=86400',
    'X-Content-Type-Options': 'nosniff'
  } });
}
