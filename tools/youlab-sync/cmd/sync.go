package cmd

import (
	"context"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"github.com/youlab/youlab-sync/internal/ralph"
	"github.com/youlab/youlab-sync/internal/sync"
)

var syncCmd = &cobra.Command{
	Use:   "sync",
	Short: "Perform a one-time sync",
	Long: `Perform a one-time bidirectional sync between the local folder
and the Ralph workspace, then exit.

This is useful for manual syncs or for running from cron/scheduled tasks.`,
	RunE: runSync,
}

func init() {
	rootCmd.AddCommand(syncCmd)
}

func runSync(cmd *cobra.Command, args []string) error {
	// Validate config
	if err := cfg.Validate(); err != nil {
		return err
	}

	logrus.Infof("Starting one-time sync")
	logrus.Infof("Local folder: %s", cfg.Sync.LocalFolder)
	logrus.Infof("Server: %s", cfg.Server.URL)

	// Create Ralph client
	client := ralph.NewClient(cfg.Server.URL, cfg.Server.APIKey, cfg.Server.UserID)

	// Create sync manager
	syncManager, err := sync.NewManager(client, cfg.Sync.LocalFolder, cfg.Ignore)
	if err != nil {
		return err
	}

	// Create context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	// Perform sync
	if err := syncManager.FullSync(ctx); err != nil {
		return err
	}

	logrus.Info("Sync completed successfully")
	return nil
}
