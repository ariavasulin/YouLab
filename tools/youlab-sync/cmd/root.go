package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"github.com/youlab/youlab-sync/internal/config"
)

var (
	cfgFile string
	cfg     *config.Config
	verbose bool
)

// rootCmd represents the base command when called without any subcommands
var rootCmd = &cobra.Command{
	Use:   "youlab-sync",
	Short: "Sync local folders with Ralph workspace",
	Long: `youlab-sync is a lightweight daemon that synchronizes files between
your local machine and your YouLab workspace.

It watches for changes in your local folder and automatically syncs them
to the Ralph server, while also pulling down changes made by the AI agent.`,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		// Set log level
		if verbose {
			logrus.SetLevel(logrus.DebugLevel)
		} else {
			logrus.SetLevel(logrus.InfoLevel)
		}

		// Load configuration
		var err error
		cfg, err = config.Load(cfgFile)
		if err != nil {
			return fmt.Errorf("failed to load config: %w", err)
		}

		// Override log level from config if not verbose
		if !verbose && cfg.Logging.Level != "" {
			level, err := logrus.ParseLevel(cfg.Logging.Level)
			if err == nil {
				logrus.SetLevel(level)
			}
		}

		return nil
	},
}

// Execute adds all child commands to the root command and sets flags appropriately.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	// Default config path
	homeDir, err := os.UserHomeDir()
	if err != nil {
		homeDir = "."
	}
	defaultConfig := filepath.Join(homeDir, ".youlab-sync", "config.yaml")

	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", defaultConfig, "config file")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "enable verbose output")
}
