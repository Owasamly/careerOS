import tailwindcss from '@tailwindcss/postcss';
import vinext from 'vinext';
import { defineConfig } from 'vite';

export default defineConfig({
  css: { postcss: { plugins: [tailwindcss()] } },
  // React PDF includes a few CommonJS transitive dependencies. Pre-bundling
  // converts their default exports into browser-safe ESM during local dev.
  optimizeDeps: {
    include: ['@react-pdf/renderer', 'base64-js', 'buffer', 'ieee754'],
  },
  plugins: [vinext()],
});
