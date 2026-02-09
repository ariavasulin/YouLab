package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"github.com/youlab/youlab-sync/internal/config"
)

var initCmd = &cobra.Command{
	Use:   "init",
	Short: "Initialize configuration",
	Long: `Initialize a new youlab-sync configuration file with default settings.

This will create a config.yaml file in ~/.youlab-sync/ that you can
customize with your server URL, API key, and local folder path.`,
	RunE: runInit,
}

var (
	initServerURL   string
	initAPIKey      string
	initUserID      string
	initLocalFolder string
	initForce       bool
)

func init() {
	rootCmd.AddCommand(initCmd)

	initCmd.Flags().StringVar(&initServerURL, "server", "http://localhost:8200", "Ralph server URL")
	initCmd.Flags().StringVar(&initAPIKey, "api-key", "", "API key for authentication")
	initCmd.Flags().StringVar(&initUserID, "user-id", "", "Your YouLab user ID")
	initCmd.Flags().StringVar(&initLocalFolder, "folder", "", "Local folder to sync")
	initCmd.Flags().BoolVar(&initForce, "force", false, "Overwrite existing config")
}

func runInit(cmd *cobra.Command, args []string) error {
	// Determine config path
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get home directory: %w", err)
	}

	configDir := filepath.Join(homeDir, ".youlab-sync")
	configPath := filepath.Join(configDir, "config.yaml")

	// Check if config already exists
	if _, err := os.Stat(configPath); err == nil && !initForce {
		return fmt.Errorf("config file already exists at %s (use --force to overwrite)", configPath)
	}

	// Create config directory
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	// Create default config
	newCfg := config.DefaultConfig()

	// Apply command-line overrides
	if initServerURL != "" {
		newCfg.Server.URL = initServerURL
	}
	if initAPIKey != "" {
		newCfg.Server.APIKey = initAPIKey
	}
	if initUserID != "" {
		newCfg.Server.UserID = initUserID
	}
	if initLocalFolder != "" {
		// Convert to absolute path
		absPath, err := filepath.Abs(initLocalFolder)
		if err != nil {
			return fmt.Errorf("failed to get absolute path: %w", err)
		}
		newCfg.Sync.LocalFolder = absPath
	}

	// Save config
	if err := newCfg.Save(configPath); err != nil {
		return err
	}

	logrus.Infof("Configuration created at %s", configPath)
	logrus.Info("")
	logrus.Info("Next steps:")
	logrus.Infof("  1. Edit %s to set your server URL and credentials", configPath)
	logrus.Info("  2. Run 'youlab-sync watch' to start syncing")

	return nil
}
