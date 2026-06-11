import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // `@/...` → `src/...`. shadcn/ui's generated components import via this alias,
    // and it keeps deep imports readable. Must match the tsconfig `paths` below.
    alias: { "@": path.resolve(__dirname, "./src") },
  },
})
