import { readFileSync } from "node:fs";
import { defineConfig } from "vite";

// the page shows the version from package.json: Vite replaces %VITE_APP_VERSION% in index.html
process.env.VITE_APP_VERSION = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8")).version;

// relative base: the build works from any subfolder of the host
export default defineConfig({
  base: "./",
  build: { chunkSizeWarningLimit: 1000 }, // three.js alone is over the default 500 kB
});
