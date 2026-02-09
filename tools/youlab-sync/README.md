# YouLab Sync Daemon

A lightweight daemon that synchronizes files between your local machine and your YouLab workspace.

## Features

- **Bidirectional Sync**: Changes made locally are uploaded; changes made by the AI agent are downloaded
- **Real-time Watching**: Uses fsnotify to detect local file changes instantly
- **Debouncing**: Prevents sync storms when files are being rapidly edited
- **Cross-platform**: Builds for macOS (arm64/amd64), Windows, and Linux
- **Lightweight**: Single static binary, < 15MB, minimal memory usage

## Installation

### From Source

```bash
cd tools/youlab-sync
go build -o youlab-sync .
```

### Cross-compilation

```bash
make build-all  # Builds for all platforms
```

## Configuration

1. Initialize configuration:
   ```bash
   ./youlab-sync init --server "https://theyoulab.org" --user-id "your-user-id" --folder "/path/to/sync"
   ```

2. Or manually create `~/.youlab-sync/config.yaml`:
   ```yaml
   server:
     url: "https://theyoulab.org"
     api_key: ""  # Optional
     user_id: "your-user-id"

   sync:
     local_folder: "/path/to/your/folder"
     interval: "30s"
     bidirectional: true

   watch:
     enabled: true
     debounce: "500ms"
   ```

## Usage

### Start Daemon (Watch Mode)

```bash
./youlab-sync watch
```

This will:
- Perform an initial full sync
- Watch for local file changes
- Periodically check for remote changes

### One-time Sync

```bash
./youlab-sync sync
```

### Check Status

```bash
./youlab-sync status
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `YOULAB_SERVER_URL` | Ralph server URL |
| `YOULAB_API_KEY` | API key for authentication |
| `YOULAB_USER_ID` | Your YouLab user ID |
| `YOULAB_LOCAL_FOLDER` | Local folder to sync |

## How It Works

1. **File Index**: The daemon maintains a local index (`.youlab-sync/index.json`) tracking the state of all synced files
2. **Hash Comparison**: Files are compared using SHA256 hashes to detect changes
3. **Conflict Resolution**: When both local and remote have changed:
   - Newer file wins (based on modification time)
   - Local is preferred on timestamp ties
4. **Deletion Tracking**: Deleted files are synced correctly using the index state

## File Types

- Text files are synced normally
- Binary files are detected and skipped
- Empty files are skipped

## Ignored Patterns

By default, these patterns are ignored:
- `.git`, `.DS_Store`, `Thumbs.db`
- `*.tmp`, `*.temp`, `*.swp`, `*.swo`, `*.log`
- `node_modules`, `__pycache__`, `.pytest_cache`

Customize in the config file's `ignore` section.

## Development

```bash
# Run tests
make test

# Run with verbose output
./youlab-sync watch -v

# Build for current platform
make build
```
