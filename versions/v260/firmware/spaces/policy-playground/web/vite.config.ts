// One file out, because the Space that serves it copies files and not trees.
//
// `scripts/publish-space.sh` publishes the *top level* of a `spaces/<name>/` directory — files and
// symlinks, `-maxdepth 1` — which is the right shape for the three Spaces that came before this
// one and the wrong shape for a bundler that emits `assets/`. Inlining everything into a single
// `index.html` keeps the published Space exactly what the console's is: a page, a Dockerfile, an
// entrypoint and a card. No build step on Hugging Face's side, nothing to get out of step.
//
// The cost is a bigger HTML file and no cache granularity, which for one page of maybe 60 KB is
// not a cost.
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [viteSingleFile()],
  // Built here and copied up by `npm run build`. Writing straight into the parent works and
  // warns on every build that the output directory contains the source — which is true, and is a
  // warning worth not teaching anybody to ignore.
  build: {
    outDir: "dist",
    target: "es2022",
  },
});
