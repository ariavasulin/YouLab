# Dev Testing SOP

## Services

| Service | Port | How to start | Auto-reload? |
|---------|------|-------------|--------------|
| Ralph server | 8200 | `make dev` or `./hack/dev.sh` | Yes (watches `src/ralph/`) |
| OpenWebUI | 3000 | Docker container `youlab-openwebui-dev` | No (rebuild + deploy) |
| Dolt | 3307 | `docker compose up -d dolt` | N/A (database) |

## Starting Development

```bash
# Start everything needed for dev
make dev          # Starts Dolt + Ralph with auto-reload

# Or manually
docker compose up -d dolt        # Database
./hack/dev.sh                    # Ralph (auto-reload)
```

Ralph auto-reloads on any change to `src/ralph/`. No manual restart needed for Python changes.

## Testing Changes

### Ralph (Python) changes

Just edit the file. Uvicorn detects the change and restarts automatically (~1s). Send a message in the browser to test.

### OpenWebUI (Svelte) changes

```bash
cd OpenWebUI/open-webui
npm run build
docker cp build/. youlab-openwebui-dev:/app/build/
```

Then hard refresh the browser (Cmd+Shift+R).

### Artifact / PDF viewer changes

The PDF viewer template lives in `src/ralph/tools/latex_templates.py` — it's a Python file, so Ralph auto-reload handles it. To test:

```bash
# Push a test PDF to the artifact panel
uv run python3 -c "
import asyncio
from pathlib import Path
from ralph.artifacts import compile_and_push
asyncio.run(compile_and_push(
    Path('/tmp/latex-test/test.tex'),
    'ed6d1437-7b38-47a4-bd49-670267f0a7ce'
))
"
```

Hard refresh (Cmd+Shift+R) then check the artifact panel.

### Memory blocks (Dolt)

```bash
# API test
USER_ID="ed6d1437-7b38-47a4-bd49-670267f0a7ce"
curl -s http://localhost:8200/users/$USER_ID/blocks | jq .

# Direct SQL
docker exec -it youlab-dolt-1 dolt sql
```

## Stopping Services

```bash
./hack/dev.sh --kill             # Stop Ralph
docker compose down              # Stop Dolt
```

## Common Issues

### "Address already in use" on port 8200
`hack/dev.sh` handles this automatically — it kills any existing process on the port before starting. If you started Ralph manually (`uv run ralph-server`), just run `./hack/dev.sh` and it will take over.

### Ralph responds instantly with empty content
The Ralph process crashed or failed to bind. Check terminal output. If running in background, check `lsof -i :8200` — if nothing is listening, restart with `./hack/dev.sh`.

### Browser not showing new changes
Hard refresh: **Cmd+Shift+R**. Regular refresh serves cached JS bundles.

### Stale Socket.IO connection
If artifact pushes return `{"status":"ok"}` but nothing appears in the browser, the Socket.IO session is stale. Hard refresh fixes it.
