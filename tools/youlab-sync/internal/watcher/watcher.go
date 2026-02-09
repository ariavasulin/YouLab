package watcher

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
	"github.com/sirupsen/logrus"
)

// Event represents a file change event
type Event struct {
	Path      string
	Operation Operation
	Time      time.Time
}

// Operation represents the type of file operation
type Operation int

const (
	OpCreate Operation = iota
	OpWrite
	OpRemove
	OpRename
)

func (o Operation) String() string {
	switch o {
	case OpCreate:
		return "create"
	case OpWrite:
		return "write"
	case OpRemove:
		return "remove"
	case OpRename:
		return "rename"
	default:
		return "unknown"
	}
}

// Watcher watches a directory for file changes with debouncing
type Watcher struct {
	rootPath       string
	ignorePatterns []string
	debounce       time.Duration
	events         chan Event
	errors         chan error
	fsWatcher      *fsnotify.Watcher

	mu            sync.Mutex
	pendingEvents map[string]*pendingEvent
	stopCh        chan struct{}
	doneCh        chan struct{}
}

type pendingEvent struct {
	event Event
	timer *time.Timer
}

// New creates a new file watcher
func New(rootPath string, ignorePatterns []string, debounce time.Duration) (*Watcher, error) {
	fsWatcher, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, err
	}

	w := &Watcher{
		rootPath:       rootPath,
		ignorePatterns: ignorePatterns,
		debounce:       debounce,
		events:         make(chan Event, 100),
		errors:         make(chan error, 10),
		fsWatcher:      fsWatcher,
		pendingEvents:  make(map[string]*pendingEvent),
		stopCh:         make(chan struct{}),
		doneCh:         make(chan struct{}),
	}

	return w, nil
}

// Events returns the channel for receiving file change events
func (w *Watcher) Events() <-chan Event {
	return w.events
}

// Errors returns the channel for receiving errors
func (w *Watcher) Errors() <-chan error {
	return w.errors
}

// Start begins watching the directory
func (w *Watcher) Start(ctx context.Context) error {
	// Add root directory and all subdirectories
	if err := w.addDirRecursive(w.rootPath); err != nil {
		return err
	}

	go w.processEvents(ctx)

	return nil
}

// Stop stops the watcher
func (w *Watcher) Stop() error {
	close(w.stopCh)
	<-w.doneCh

	// Cancel all pending timers
	w.mu.Lock()
	for _, pe := range w.pendingEvents {
		pe.timer.Stop()
	}
	w.pendingEvents = nil
	w.mu.Unlock()

	close(w.events)
	close(w.errors)

	return w.fsWatcher.Close()
}

func (w *Watcher) processEvents(ctx context.Context) {
	defer close(w.doneCh)

	for {
		select {
		case <-ctx.Done():
			return
		case <-w.stopCh:
			return
		case event, ok := <-w.fsWatcher.Events:
			if !ok {
				return
			}
			w.handleFSEvent(event)
		case err, ok := <-w.fsWatcher.Errors:
			if !ok {
				return
			}
			select {
			case w.errors <- err:
			default:
				logrus.Warnf("Error channel full, dropping error: %v", err)
			}
		}
	}
}

func (w *Watcher) handleFSEvent(event fsnotify.Event) {
	// Convert to relative path
	relPath, err := filepath.Rel(w.rootPath, event.Name)
	if err != nil {
		logrus.Warnf("Failed to get relative path for %s: %v", event.Name, err)
		return
	}

	// Check if path should be ignored
	if w.shouldIgnore(relPath) {
		logrus.Debugf("Ignoring event for: %s", relPath)
		return
	}

	// Determine operation type
	var op Operation
	switch {
	case event.Has(fsnotify.Create):
		op = OpCreate
		// If a directory was created, watch it recursively
		if info, err := os.Stat(event.Name); err == nil && info.IsDir() {
			w.addDirRecursive(event.Name)
		}
	case event.Has(fsnotify.Write):
		op = OpWrite
	case event.Has(fsnotify.Remove):
		op = OpRemove
	case event.Has(fsnotify.Rename):
		op = OpRename
	default:
		return
	}

	// Debounce the event
	w.debounceEvent(Event{
		Path:      relPath,
		Operation: op,
		Time:      time.Now(),
	})
}

func (w *Watcher) debounceEvent(event Event) {
	w.mu.Lock()
	defer w.mu.Unlock()

	// Cancel existing timer for this path
	if existing, ok := w.pendingEvents[event.Path]; ok {
		existing.timer.Stop()
	}

	// Create new timer
	pe := &pendingEvent{
		event: event,
	}

	pe.timer = time.AfterFunc(w.debounce, func() {
		w.mu.Lock()
		delete(w.pendingEvents, event.Path)
		w.mu.Unlock()

		select {
		case w.events <- pe.event:
		default:
			logrus.Warnf("Events channel full, dropping event for: %s", pe.event.Path)
		}
	})

	w.pendingEvents[event.Path] = pe
}

func (w *Watcher) addDirRecursive(root string) error {
	return filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Get relative path for ignore check
		relPath, err := filepath.Rel(w.rootPath, path)
		if err != nil {
			relPath = path
		}

		// Skip ignored directories
		if info.IsDir() && w.shouldIgnore(relPath) {
			return filepath.SkipDir
		}

		// Only watch directories
		if info.IsDir() {
			if err := w.fsWatcher.Add(path); err != nil {
				logrus.Warnf("Failed to watch directory %s: %v", path, err)
			} else {
				logrus.Debugf("Watching directory: %s", path)
			}
		}

		return nil
	})
}

func (w *Watcher) shouldIgnore(path string) bool {
	// Check each component of the path
	parts := strings.Split(path, string(filepath.Separator))

	for _, pattern := range w.ignorePatterns {
		// Check if any path component matches the pattern
		for _, part := range parts {
			matched, err := filepath.Match(pattern, part)
			if err == nil && matched {
				return true
			}
		}

		// Also check the full path
		matched, err := filepath.Match(pattern, filepath.Base(path))
		if err == nil && matched {
			return true
		}
	}

	return false
}
