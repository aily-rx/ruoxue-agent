/**
 * Sanity tests — verify essential project metadata and config.
 * Does NOT import app source code (Live2D SDK requires WebGL).
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

const PROJECT_ROOT = path.resolve(import.meta.dirname, "..");

describe("Project files", () => {
  it("package.json exists and is valid", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(PROJECT_ROOT, "package.json"), "utf-8"),
    );
    expect(pkg.name).toBe("ruoxue-frontend");
    expect(pkg.scripts.dev).toBeDefined();
    expect(pkg.scripts.build).toBeDefined();
    expect(pkg.scripts.test).toBeDefined();
    expect(pkg.scripts.lint).toBeDefined();
  });

  it("tsconfig.json exists", () => {
    const exists = fs.existsSync(path.join(PROJECT_ROOT, "tsconfig.json"));
    expect(exists).toBe(true);
  });
});

describe("Source structure", () => {
  it("main entry point exists", () => {
    const exists = fs.existsSync(path.join(PROJECT_ROOT, "src", "main.tsx"));
    expect(exists).toBe(true);
  });

  it("core components exist", () => {
    const compDir = path.join(PROJECT_ROOT, "src", "components");
    expect(fs.existsSync(path.join(compDir, "ChatPanel.tsx"))).toBe(true);
    expect(fs.existsSync(path.join(compDir, "Live2DCanvas.tsx"))).toBe(true);
    expect(fs.existsSync(path.join(compDir, "VoiceButton.tsx"))).toBe(true);
  });
});
