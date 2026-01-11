# OpenWebUI Development

[[README|← Back to Overview]]

Guide for modifying the OpenWebUI frontend.

## Key Insight

**Don't use Docker for frontend development.** OpenWebUI has native dev mode with instant hot-reloading.

## Project Location

OpenWebUI is a **nested git repository** at `OpenWebUI/open-webui/`:
- Origin: `https://github.com/open-webui/open-webui`
- Not a submodule—requires separate commits/PRs
- Data persists in `backend/data/`

## Native Development (Recommended)

### Start Servers

**Terminal 1 - Backend** (port 8080):
```bash
cd OpenWebUI/open-webui/backend
./dev.sh
```

**Terminal 2 - Frontend** (port 5173):
```bash
cd OpenWebUI/open-webui
npm install  # first time only
npm run dev
```

**Browser**: http://localhost:5173

Frontend proxies API calls to `localhost:8080` automatically in dev mode.

### Workflow Comparison

| Task | Docker | Native Dev |
|------|--------|------------|
| Edit Svelte component | 5-10 min rebuild | <100ms hot reload |
| See changes | Restart container | Instant |
| Debug issues | Rebuild from scratch | Fix and continue |

## Key Files

| File | Purpose |
|------|---------|
| `src/lib/components/layout/Sidebar.svelte` | Main sidebar |
| `src/lib/i18n/locales/en-US/translation.json` | Translations |
| `src/lib/components/icons/*.svelte` | Icon components |
| `backend/dev.sh` | Backend dev script |
| `backend/data/webui.db` | SQLite database |

## Docker (Production Only)

Use Docker only for production builds.

### Common Build Issues

| Issue | Fix |
|-------|-----|
| `Missing: picomatch from lock file` | `git checkout package.json package-lock.json` |
| `JavaScript heap out of memory` | Add to Dockerfile: `ENV NODE_OPTIONS="--max-old-space-size=4096"` |
| `Cypress download failed` | Add to Dockerfile: `ENV CYPRESS_INSTALL_BINARY=0` |

### Build Commands

```bash
cd OpenWebUI/open-webui
docker compose build open-webui
docker compose up -d open-webui
```

## Related Pages

- [[Pipeline]] - YouLab/OpenWebUI integration
- [[Architecture]] - System overview
