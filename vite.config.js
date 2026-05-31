import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',   // Electron은 상대경로 필요
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api/kis': {
        target: 'https://openapi.koreainvestment.com:9443',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/kis/, ''),
        secure: true,
      },
    },
  },
});
