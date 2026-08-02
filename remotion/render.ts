/**
 * render.ts — Remotion render entry point called by Python via subprocess.
 *
 * Usage:
 *   ts-node render.ts --scene-data '{"outputPath":"out.mp4","compositionFile":"VideoComposition","durationInFrames":420}'
 *   echo '{"outputPath":"out.mp4","compositionFile":"VideoComposition","durationInFrames":420}' | ts-node render.ts
 *
 * On success:  prints the resolved output path to stdout and exits 0.
 * On failure:  prints an error message to stderr and exits 1.
 */

import path from "path";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

interface SceneData {
  /** Absolute or relative path for the rendered output file */
  outputPath: string;
  /** Remotion composition ID (e.g. "VideoComposition") */
  compositionFile: string;
  /** Total duration in frames */
  durationInFrames: number;
  /** Optional: frames-per-second override (default 30) */
  fps?: number;
  /** Optional: video width override (default 1080) */
  width?: number;
  /** Optional: video height override (default 1920) */
  height?: number;
  /** Optional: CRF quality (lower = better, default 18) */
  crf?: number;
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function parseArgs(): Partial<SceneData> {
  const args = process.argv.slice(2);
  const sceneDataFlagIdx = args.findIndex((a) => a === "--scene-data");
  if (sceneDataFlagIdx !== -1 && args[sceneDataFlagIdx + 1]) {
    try {
      return JSON.parse(args[sceneDataFlagIdx + 1]) as Partial<SceneData>;
    } catch (err) {
      throw new Error(
        `Failed to parse --scene-data JSON: ${(err as Error).message}`
      );
    }
  }
  return {};
}

async function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data.trim()));
    process.stdin.on("error", reject);
  });
}

async function resolveSceneData(): Promise<SceneData> {
  // 1. Try --scene-data CLI flag first
  const fromArgs = parseArgs();
  if (fromArgs.outputPath && fromArgs.compositionFile) {
    return fromArgs as SceneData;
  }

  // 2. Fall back to stdin
  const raw = await readStdin();
  if (!raw) {
    throw new Error(
      "No scene data provided. Pass --scene-data '<json>' or pipe JSON to stdin."
    );
  }

  let parsed: Partial<SceneData>;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`Failed to parse stdin JSON: ${(err as Error).message}`);
  }

  if (!parsed.outputPath) {
    throw new Error("scene data must include 'outputPath'");
  }
  if (!parsed.compositionFile) {
    throw new Error("scene data must include 'compositionFile'");
  }

  return parsed as SceneData;
}

// ─────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const sceneData = await resolveSceneData();

  const {
    outputPath,
    compositionFile,
    durationInFrames,
    fps = 30,
    width = 1080,
    height = 1920,
    crf = 18,
  } = sceneData;

  const resolvedOutput = path.resolve(outputPath);

  // Entry point for the Remotion bundle
  const entryPoint = path.resolve(__dirname, "src", "index.ts");

  process.stderr.write(
    `[render] Bundling entry point: ${entryPoint}\n`
  );

  // Bundle the project
  const bundled = await bundle({
    entryPoint,
    // Pass the remotion config so settings are applied
    webpackOverride: (config) => config,
  });

  process.stderr.write(
    `[render] Selecting composition: ${compositionFile}\n`
  );

  // Select the composition
  const composition = await selectComposition({
    serveUrl: bundled,
    id: compositionFile,
    inputProps: {},
  });

  // Override duration if provided
  const finalDuration =
    durationInFrames > 0 ? durationInFrames : composition.durationInFrames;

  process.stderr.write(
    `[render] Rendering ${finalDuration} frames @ ${fps}fps → ${resolvedOutput}\n`
  );

  await renderMedia({
    composition: {
      ...composition,
      durationInFrames: finalDuration,
      fps,
      width,
      height,
    },
    serveUrl: bundled,
    codec: "h264",
    outputLocation: resolvedOutput,
    crf,
    onProgress: ({ progress }) => {
      const pct = Math.round(progress * 100);
      process.stderr.write(`[render] Progress: ${pct}%\r`);
    },
  });

  process.stderr.write("\n[render] Done.\n");

  // Print resolved output path to stdout for the Python caller to read
  process.stdout.write(resolvedOutput + "\n");
}

main().catch((err: Error) => {
  process.stderr.write(`[render] ERROR: ${err.message}\n`);
  if (err.stack) {
    process.stderr.write(err.stack + "\n");
  }
  process.exit(1);
});
