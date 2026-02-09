package cmd

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"github.com/youlab/youlab-sync/internal/ralph"
	"github.com/youlab/youlab-sync/internal/sync"
	"github.com/youlab/youlab-sync/internal/watcher"
)

var watchCmd = &cobra.Command{
	Use:   "watch",
	Short: "Watch local folder and sync changes",
	Long: `Watch the configured local folder for changes and synchronize them
with the Ralph workspace. This is the main daemon mode.

The daemon will:
- Perform an initial full sync on startup
- Watch for local file changes and upload them
- Periodically check for remote changes and download them`,
	RunE: runWatch,
}

func init() {
	rootCmd.AddCommand(watchCmd)
}

func runWatch(cmd *cobra.Command, args []string) error {
	// Validate config
	if err := cfg.Validate(); err != nil {
		return err
	}

	logrus.Infof("Starting youlab-sync daemon")
	logrus.Infof("Local folder: %s", cfg.Sync.LocalFolder)
	logrus.Infof("Server: %s", cfg.Server.URL)
	logrus.Infof("User ID: %s", cfg.Server.UserID)

	// Create Ralph client
	client := ralph.NewClient(cfg.Server.URL, cfg.Server.APIKey, cfg.Server.UserID)

	// Create sync manager
	syncManager, err := sync.NewManager(client, cfg.Sync.LocalFolder, cfg.Ignore)
	if err != nil {
		return err
	}

	// Create context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Set up signal handling
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	// Perform initial sync
	logrus.Info("Performing initial sync...")
	if err := syncManager.FullSync(ctx); err != nil {
		logrus.Errorf("Initial sync failed: %v", err)
		// Continue even if initial sync fails
	}

	// Start file watcher if enabled
	var fileWatcher *watcher.Watcher
	if cfg.Watch.Enabled {
		fileWatcher, err = watcher.New(cfg.Sync.LocalFolder, cfg.Ignore, cfg.Watch.Debounce)
		if err != nil {
			return err
		}

		if err := fileWatcher.Start(ctx); err != nil {
			return err
		}
		defer fileWatcher.Stop()

		logrus.Info("File watcher started")

		// Handle file watcher events
		go func() {
			for {
				select {
				case <-ctx.Done():
					return
				case event, ok := <-fileWatcher.Events():
					if !ok {
						return
					}
					logrus.Debugf("File change detected: %s (%s)", event.Path, event.Operation)
					if err := syncManager.HandleLocalChange(ctx, event); err != nil {
						logrus.Errorf("Failed to handle local change: %v", err)
					}
				case err, ok := <-fileWatcher.Errors():
					if !ok {
						return
					}
					logrus.Errorf("Watcher error: %v", err)
				}
			}
		}()
	}

	// Start periodic sync for bidirectional mode
	var syncTicker *time.Ticker
	if cfg.Sync.Bidirectional && cfg.Sync.Interval > 0 {
		syncTicker = time.NewTicker(cfg.Sync.Interval)
		defer syncTicker.Stop()

		go func() {
			for {
				select {
				case <-ctx.Done():
					return
				case <-syncTicker.C:
					logrus.Debug("Running periodic sync...")
					if err := syncManager.FullSync(ctx); err != nil {
						logrus.Errorf("Periodic sync failed: %v", err)
					}
				}
			}
		}()

		logrus.Infof("Periodic sync enabled (interval: %s)", cfg.Sync.Interval)
	}

	logrus.Info("Daemon ready. Press Ctrl+C to stop.")

	// Wait for shutdown signal
	<-sigCh
	logrus.Info("Shutting down...")
	cancel()

	// Give some time for cleanup
	time.Sleep(500 * time.Millisecond)

	logrus.Info("Goodbye!")
	return nil
}
