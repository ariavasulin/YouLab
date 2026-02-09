package sync

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/youlab/youlab-sync/internal/ralph"
	"github.com/youlab/youlab-sync/internal/watcher"
)

// FileState represents the sync state of a file
type FileState struct {
	Path     string    `json:"path"`
	Hash     string    `json:"hash"`
	Size     int64     `json:"size"`
	Modified time.Time `json:"modified"`
	Source   string    `json:"source"` // "local" or "remote"
	SyncedAt time.Time `json:"synced_at"`
}

// SyncIndex stores the state of all synced files
type SyncIndex struct {
	Version  int                   `json:"version"`
	UserID   string                `json:"user_id"`
	LastSync time.Time             `json:"last_sync"`
	Files    map[string]*FileState `json:"files"`
}

// Manager handles bidirectional file synchronization
type Manager struct {
	client         *ralph.Client
	localPath      string
	ignorePatterns []string
	indexPath      string

	mu    sync.RWMutex
	index *SyncIndex
}

// NewManager creates a new sync manager
func NewManager(client *ralph.Client, localPath string, ignorePatterns []string) (*Manager, error) {
	m := &Manager{
		client:         client,
		localPath:      localPath,
		ignorePatterns: ignorePatterns,
		indexPath:      filepath.Join(localPath, ".youlab-sync", "index.json"),
		index: &SyncIndex{
			Version: 1,
			Files:   make(map[string]*FileState),
		},
	}

	// Ensure sync directory exists
	syncDir := filepath.Dir(m.indexPath)
	if err := os.MkdirAll(syncDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create sync directory: %w", err)
	}

	// Load existing index
	if err := m.loadIndex(); err != nil {
		logrus.Warnf("Failed to load sync index: %v", err)
	}

	return m, nil
}

// FullSync performs a complete bidirectional sync
func (m *Manager) FullSync(ctx context.Context) error {
	logrus.Info("Starting full sync...")

	// Get remote file list
	remoteIndex, err := m.client.ListFiles(ctx)
	if err != nil {
		return fmt.Errorf("failed to get remote file list: %w", err)
	}

	// Get local file list
	localFiles, err := m.scanLocalFiles()
	if err != nil {
		return fmt.Errorf("failed to scan local files: %w", err)
	}

	// Build sets of all paths
	allPaths := make(map[string]bool)
	for path := range remoteIndex.Files {
		allPaths[path] = true
	}
	for path := range localFiles {
		allPaths[path] = true
	}

	// Process each file
	for path := range allPaths {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		var remoteMeta *ralph.FileMetadata
		if r, ok := remoteIndex.Files[path]; ok {
			remoteMeta = &r
		}
		local := localFiles[path]
		indexed := m.getIndexedState(path)

		if err := m.syncFile(ctx, path, remoteMeta, local, indexed); err != nil {
			logrus.Errorf("Failed to sync file %s: %v", path, err)
			continue
		}
	}

	m.mu.Lock()
	m.index.LastSync = time.Now()
	m.mu.Unlock()

	if err := m.saveIndex(); err != nil {
		logrus.Errorf("Failed to save sync index: %w", err)
	}

	logrus.Info("Full sync completed")
	return nil
}

// HandleLocalChange processes a local file change event
func (m *Manager) HandleLocalChange(ctx context.Context, event watcher.Event) error {
	logrus.Debugf("Handling local change: %s (%s)", event.Path, event.Operation)

	switch event.Operation {
	case watcher.OpCreate, watcher.OpWrite:
		return m.uploadFile(ctx, event.Path)
	case watcher.OpRemove:
		return m.deleteRemoteFile(ctx, event.Path)
	case watcher.OpRename:
		// Rename is handled as delete + create by fsnotify
		return nil
	}

	return nil
}

func (m *Manager) syncFile(ctx context.Context, path string, remote *ralph.FileMetadata, local *FileState, indexed *FileState) error {
	logrus.Debugf("Syncing %s: remote=%v local=%v indexed=%v", path, remote != nil, local != nil, indexed != nil)

	switch {
	case remote != nil && local != nil:
		// File exists on both sides - check which is newer
		if local.Hash == remote.Hash {
			// Same content, just update index
			m.updateIndex(path, local.Hash, local.Size, local.Modified, "both")
			return nil
		}

		// Different content - resolve conflict
		// Use last-modified time, prefer local on tie
		if local.Modified.After(remote.Modified) {
			logrus.Infof("Local file newer, uploading: %s", path)
			return m.uploadFile(ctx, path)
		} else if remote.Modified.After(local.Modified) {
			logrus.Infof("Remote file newer, downloading: %s", path)
			return m.downloadFile(ctx, path)
		} else {
			// Same modification time but different content - prefer local
			logrus.Infof("Conflict resolved (prefer local): %s", path)
			return m.uploadFile(ctx, path)
		}

	case remote != nil && local == nil:
		// File exists only on remote
		if indexed != nil {
			// We had it before, it was deleted locally - delete remote
			logrus.Infof("File deleted locally, removing from remote: %s", path)
			return m.deleteRemoteFile(ctx, path)
		}
		// New file from remote - download
		logrus.Infof("New remote file, downloading: %s", path)
		return m.downloadFile(ctx, path)

	case remote == nil && local != nil:
		// File exists only locally
		if indexed != nil {
			// We had it before, it was deleted remotely - delete local
			logrus.Infof("File deleted remotely, removing locally: %s", path)
			return m.deleteLocalFile(path)
		}
		// New local file - upload
		logrus.Infof("New local file, uploading: %s", path)
		return m.uploadFile(ctx, path)

	case remote == nil && local == nil:
		// File doesn't exist anywhere - clean up index
		m.removeFromIndex(path)
		return nil
	}

	return nil
}

func (m *Manager) uploadFile(ctx context.Context, relPath string) error {
	fullPath := filepath.Join(m.localPath, relPath)

	content, err := os.ReadFile(fullPath)
	if err != nil {
		return fmt.Errorf("failed to read file: %w", err)
	}

	// Skip empty files
	if len(content) == 0 {
		logrus.Warnf("Skipping empty file: %s", relPath)
		return nil
	}

	// Skip binary files
	if isBinaryFile(content) {
		logrus.Debugf("Skipping binary file: %s", relPath)
		return nil
	}

	metadata, err := m.client.PutFile(ctx, relPath, content)
	if err != nil {
		return fmt.Errorf("failed to upload file: %w", err)
	}

	info, err := os.Stat(fullPath)
	if err != nil {
		return fmt.Errorf("failed to stat file: %w", err)
	}

	m.updateIndex(relPath, metadata.Hash, metadata.Size, info.ModTime(), "local")
	logrus.Infof("Uploaded: %s", relPath)
	return nil
}

func (m *Manager) downloadFile(ctx context.Context, relPath string) error {
	content, metadata, err := m.client.GetFile(ctx, relPath)
	if err != nil {
		return fmt.Errorf("failed to download file: %w", err)
	}

	if content == nil {
		// File was deleted on remote
		return m.deleteLocalFile(relPath)
	}

	fullPath := filepath.Join(m.localPath, relPath)

	// Create directory if needed
	dir := filepath.Dir(fullPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create directory: %w", err)
	}

	if err := os.WriteFile(fullPath, content, 0644); err != nil {
		return fmt.Errorf("failed to write file: %w", err)
	}

	// Set modification time to match remote
	if !metadata.Modified.IsZero() {
		if err := os.Chtimes(fullPath, metadata.Modified, metadata.Modified); err != nil {
			logrus.Warnf("Failed to set file modification time: %v", err)
		}
	}

	m.updateIndex(relPath, metadata.Hash, metadata.Size, metadata.Modified, "remote")
	logrus.Infof("Downloaded: %s", relPath)
	return nil
}

func (m *Manager) deleteLocalFile(relPath string) error {
	fullPath := filepath.Join(m.localPath, relPath)

	if err := os.Remove(fullPath); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("failed to delete local file: %w", err)
	}

	m.removeFromIndex(relPath)
	logrus.Infof("Deleted locally: %s", relPath)
	return nil
}

func (m *Manager) deleteRemoteFile(ctx context.Context, relPath string) error {
	if err := m.client.DeleteFile(ctx, relPath); err != nil {
		return fmt.Errorf("failed to delete remote file: %w", err)
	}

	m.removeFromIndex(relPath)
	logrus.Infof("Deleted remotely: %s", relPath)
	return nil
}

func (m *Manager) scanLocalFiles() (map[string]*FileState, error) {
	files := make(map[string]*FileState)

	err := filepath.WalkDir(m.localPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil // Skip errors
		}

		// Get relative path
		relPath, err := filepath.Rel(m.localPath, path)
		if err != nil {
			return nil
		}

		// Skip the sync directory itself
		if strings.HasPrefix(relPath, ".youlab-sync") {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		// Skip ignored files/directories
		if m.shouldIgnore(relPath) {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		// Skip directories
		if d.IsDir() {
			return nil
		}

		// Read file
		content, err := os.ReadFile(path)
		if err != nil {
			logrus.Warnf("Failed to read file %s: %v", path, err)
			return nil
		}

		// Skip binary files
		if isBinaryFile(content) {
			return nil
		}

		info, err := d.Info()
		if err != nil {
			return nil
		}

		hash := calculateHash(content)

		files[relPath] = &FileState{
			Path:     relPath,
			Hash:     hash,
			Size:     info.Size(),
			Modified: info.ModTime(),
			Source:   "local",
		}

		return nil
	})

	return files, err
}

func (m *Manager) shouldIgnore(path string) bool {
	parts := strings.Split(path, string(filepath.Separator))

	for _, pattern := range m.ignorePatterns {
		for _, part := range parts {
			if matched, _ := filepath.Match(pattern, part); matched {
				return true
			}
		}

		if matched, _ := filepath.Match(pattern, filepath.Base(path)); matched {
			return true
		}
	}

	return false
}

func (m *Manager) getIndexedState(path string) *FileState {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.index.Files[path]
}

func (m *Manager) updateIndex(path, hash string, size int64, modified time.Time, source string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.index.Files[path] = &FileState{
		Path:     path,
		Hash:     hash,
		Size:     size,
		Modified: modified,
		Source:   source,
		SyncedAt: time.Now(),
	}
}

func (m *Manager) removeFromIndex(path string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.index.Files, path)
}

func (m *Manager) loadIndex() error {
	data, err := os.ReadFile(m.indexPath)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	return json.Unmarshal(data, m.index)
}

func (m *Manager) saveIndex() error {
	m.mu.RLock()
	data, err := json.MarshalIndent(m.index, "", "  ")
	m.mu.RUnlock()

	if err != nil {
		return err
	}

	return os.WriteFile(m.indexPath, data, 0644)
}

func calculateHash(content []byte) string {
	hash := sha256.Sum256(content)
	return fmt.Sprintf("%x", hash)
}

func isBinaryFile(content []byte) bool {
	if len(content) == 0 {
		return false
	}

	// Check for null bytes (common in binary files)
	checkLen := len(content)
	if checkLen > 1024 {
		checkLen = 1024
	}

	for i := 0; i < checkLen; i++ {
		if content[i] == 0 {
			return true
		}
	}

	// Check for high ratio of non-printable characters
	nonPrintable := 0
	for i := 0; i < checkLen; i++ {
		if content[i] < 32 && content[i] != 9 && content[i] != 10 && content[i] != 13 {
			nonPrintable++
		}
	}

	return float64(nonPrintable)/float64(checkLen) > 0.3
}
