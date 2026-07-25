# Agent.md — Shared Knowledge Base

> Automatically maintained by Claude Code and other coding tools.
> Serves as the single source of truth for reusable patterns, best practices, and bug fixes across both frontend and backend.

---

## 📋 Usage

This file is a **global index** that points to detailed experience documents stored in the respective `experience/` directories. When a major feature is completed or an important bug is fixed, the corresponding experience is automatically synced to:

- **Frontend** → `docs/frontend/experience/`
- **Backend** → `docs/backend/experience/`

Each experience file follows a standardized template (see `_TEMPLATE.md` in each experience directory).

---

## 🏗 Generation Rules

Reusable generation instructions: prompt templates, naming conventions, file organization conventions.

### Naming Conventions

| Layer | File Naming | Example |
|-------|-------------|---------|
| Core modules | `PascalCase.js` | `Renderer.js`, `Camera.js`, `Scene.js` |
| Infrastructure | `PascalCase.js` | `AssetManager.js`, `EventBus.js` |
| Business modules | `PascalCase.js` | `Avatar.js`, `UIManager.js` |
| CSS files | `kebab-case.css` | `style.css`, `debug.css` |
| Experience docs | `kebab-case-description.md` | `ascii-layout-techniques.md` |
| Vue components (future) | `PascalCase.vue` | `ChatPanel.vue` |

### File Organization Conventions

```
project/
├── docs/
│   ├── frontend/experience/    ← Frontend reusable knowledge
│   └── backend/experience/     ← Backend reusable knowledge
├── src/                        ← Source code by layer (not by type)
│   ├── core/                   ← Three.js thin wrappers
│   ├── infrastructure/         ← Cross-cutting concerns
│   ├── avatar/                 ← Business domain: character
│   ├── interaction/            ← Business domain: user input
│   └── utils/                  ← Dev/debug utilities
```

### Architecture Rules

- **Dependency direction**: Upper layers depend on lower layers. Core only depends on external libraries (Three.js).
- **Module pattern**: Each module exports a class that wraps a Three.js object via `.instance`.
- **Inter-module communication**: Pub/sub via `EventBus` — no direct cross-layer imports.
- **CSS design tokens**: All visual values defined as CSS custom properties in `:root` — never hardcode colors/spacing/shadows.

---

## 📖 Experience Index

### Frontend (`docs/frontend/experience/`)

| Document | Description | Date |
|----------|-------------|------|
| [`frontend-layout-design.md`](docs/frontend/experience/frontend-layout-design.md) | Front-end layout design methodology: from architecture to prototype, PC/Mobile unified strategy, CSS Grid patterns, DEBUG panel design, interaction mapping | 2026-07-20 |
| [`ascii-layout-techniques.md`](docs/frontend/experience/ascii-layout-techniques.md) | ASCII art layout techniques: box-drawing symbols, annotation conventions, multi-state coverage, workflow | 2026-07-20 |
| [`sidebar-overlay-pattern.md`](docs/frontend/experience/sidebar-overlay-pattern.md) | Sidebar overlay pattern: using position:absolute to overlay UI panels on 3D viewport without affecting canvas aspect ratio | 2026-07-22 |

### Backend (`docs/backend/experience/`)

| Document | Description | Date |
|----------|-------------|------|
| [`g2pM-viseme-pipeline.md`](docs/backend/experience/g2pM-viseme-pipeline.md) | g2pM + Edge TTS WordBoundary: text-to-phoneme pipeline with custom viseme table in config.ini | 2026-07-22 |
| [`config-ini-consolidation.md`](docs/backend/experience/config-ini-consolidation.md) | Backend config consolidation: migrate from .env + hardcoded to config.ini using stdlib configparser | 2026-07-22 |

---

## 🐛 Bug Fix Index

> Each entry links to a detailed bug report in the corresponding `experience/` directory, containing: symptoms → root cause → fix → prevention.

| # | Module | Symptom | Root Cause | Fix | Date |
|---|--------|---------|------------|-----|------|
| 1 | [`blendshape-index-cross-contamination`](docs/frontend/experience/blendshape-index-cross-contamination.md) | Avatar head meshes disappear/deform during speech | Shared morphMap index applied across all head meshes; different meshes have different morph targets at same index | Use per-mesh morphTargetDictionary for index lookup; add exponential smoothing to cue-mode weight transitions | 2026-07-22 |
| 2 | [`live2d-white-rectangle-fix`](docs/frontend/experience/live2d-white-rectangle-fix.md) | Live2D model shows white rectangles over body/hair/clothing | Premultiplied alpha mismatch: WebGL context `premultipliedAlpha:false`, renderer `isPremultipliedAlpha=false`, texture not premultiplied | Set context `premultipliedAlpha:true`, call `setIsPremultipliedAlpha(true)`, use `UNPACK_PREMULTIPLY_ALPHA_WEBGL` during texture upload | 2026-07-24 |
| 3 | [`live2d-ghosting-fix`](docs/frontend/experience/live2d-ghosting-fix.md) | Live2D model appears doubled (ghosting), like two copies overlapping | Missing Physics + Pose data loading and `CubismUpdateScheduler` pipeline; model parameters at incorrect defaults causing mask offset | Load physics3.json + pose3.json, create Physics/Pose updaters, register in CubismUpdateScheduler, call `onLateUpdate()` before `_model.update()` | 2026-07-24 |
| 4 | [`live2d-emotion-driver-fix`](docs/frontend/experience/live2d-emotion-driver-fix.md) | Emotion expressions not visible, thinking expression doesn't show, reset button broken | 5 root causes: (1) parameter names don't match model, (2) expression index mapping guessed wrong, (3) two-phase transition drove unrelated params to 0, (4) reset set params to 0 instead of model defaults, (5) ref-based setEmotion bypassed React state | Read .exp3.json to get actual params & remap emotion→index, only drive emotion-specific params in transition, use `loadParameters()` for reset, remove auto-reset effect, add two-phase transition (neutral→target) | 2026-07-24 |
| 5 | [`live2d-emotion-transition-v2`](docs/frontend/experience/live2d-emotion-transition-v2.md) | Neutral transition half-closes eyes; emotion switching looks jarring; Phase 2 targets silently cleared | (1) intensity scaled neutral causing eye=0.3, (2) neutral used two-phase path needlessly, (3) instant expression preset clashed with smooth param lerp, (4) same-frame race between Phase 2 trigger and cleanup check | Neutral: single-phase, skip intensity; defer expression preset to transition end; reorder cleanup check before Phase 2 trigger | 2026-07-24 |

---

## ✅ Phase Completion Summaries

| Phase | Summary | Status | Date |
|-------|---------|--------|------|
| Phase 3 | [`phase3-summary.md`](docs/phase3-summary.md) — Live2D digital human: deliverables, architecture decisions, bug fix history, remaining issues, Phase 4 handoff | ✅ Done | 2026-07-25 |
| Phase 2 | [`phase2-summary.md`](docs/phase2-summary.md) — Voice interaction: ASR/TTS/G2P/Viseme pipeline, recording/playback, audio-viseme sync | ✅ Done | 2026-07-25 |
| Phase 1 | [`phase1-summary.md`](docs/phase1-summary.md) — Text chat: SSE streaming, emotion tags, conversation memory, chat UI, state management | ✅ Done | 2026-07-25 |

---

## 🔄 Auto-Sync Trigger Mechanism

When one of the following events occurs, relevant experience should be automatically extracted and synced:

### Trigger Events
1. **Major feature completion** — New module, architecture change, or significant UI overhaul
2. **Important bug fix** — Non-trivial bug that took >30min to resolve or reveals a systematic issue
3. **Design decision** — Trade-off or constraint that affects future development
4. **Performance optimization** — Measurable improvement with methodology worth reusing

### Sync Action
```
1. Identify the experience type (frontend/backend)
2. Create/update the experience doc in the corresponding directory
3. Update the index tables above (Experience Index / Bug Fix Index)
4. Cross-reference related docs (add "See also" links)
```

### Experience Document Format
Every experience file should include:
```markdown
# Title (brief, descriptive)

> Source: [Project Name] | Date: YYYY-MM-DD
> Tags: [domain, technology, pattern]

---

## Context
(What problem were we solving? What was the situation?)

## Approach / Solution
(What did we do? Why this approach?)

## Key Insights
(Bullet points of reusable lessons)

## Pitfalls / Anti-patterns
(What went wrong? What should others avoid?)

## See Also
(Links to related experience docs)
```

---

## 📂 Full Directory Map

```
Agent.md                                  ← THIS FILE: shared knowledge base index
CLAUDE.md                                 ← Claude Code workspace guide (project overview, commands, architecture)
docs/
├── architecture.md                       ← Full architecture design document
├── project-structure.md                  ← Complete directory tree
├── frontend/
│   ├── prototype-layout.md             ← ASCII layout diagrams for all page states
│   └── experience/
├── backend/
│   ├── architecture.md                 ← Backend architecture (lip-sync)
│   ├── prd-lipsync.md                  ← Lip-sync PRD
│   └── experience/
├── frontend/
│   └── experience/                       ← Frontend reusable knowledge
│       ├── _TEMPLATE.md                  ← Experience doc template
│       ├── frontend-layout-design.md     ← Layout design methodology
│       └── ascii-layout-techniques.md    ← ASCII art techniques
└── backend/
    └── experience/                       ← Backend reusable knowledge (future)
        └── _TEMPLATE.md                  ← Experience doc template
```

---

*Last updated: 2026-07-21 — This file is automatically maintained. Do not edit manually unless adding project-wide rules.*
