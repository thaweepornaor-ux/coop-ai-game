import { defineConfig } from 'vite';
import vinext from 'vinext';
process.env.CLOUDFLARE_CF_FETCH_ENABLED ??= 'false';
process.env.WRANGLER_SEND_METRICS ??= 'false';
export default defineConfig(async () => {
  const { cloudflare } = await import('@cloudflare/vite-plugin');
  return {
    plugins: [vinext(), cloudflare({
      configPath: './.staging-local/wrangler.staging.json',
      viteEnvironment: { name: 'rsc', childEnvironments: ['ssr'] },
      remoteBindings: false,
      inspectorPort: false,
    })],
  };
});
