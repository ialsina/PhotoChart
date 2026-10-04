import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const djangoDevServer = process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Same-origin session + CSRF (see backend/auth_views.py); mirrors deploy/nginx.conf API paths.
      '/api': {
        target: djangoDevServer,
        changeOrigin: false,
      },
      '/media': {
        target: djangoDevServer,
        changeOrigin: false,
      },
    },
  },
})
