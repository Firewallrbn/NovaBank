import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// El backend real corre en :8000. En desarrollo se hace proxy para que el
// frontend hable siempre contra rutas relativas /api, igual que en producción
// (donde nginx hace el mismo proxy dentro de la red de Docker).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
