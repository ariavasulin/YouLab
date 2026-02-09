package cmd

import (
	"context"
	"fmt"
	"time"

	"github.com/spf13/cobra"
	"github.com/youlab/youlab-sync/internal/ralph"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show sync status",
	Long: `Show the current sync status including:
- Connection status to the Ralph server
- Number of files in the workspace
- Last sync time`,
	RunE: runStatus,
}

func init() {
	rootCmd.AddCommand(statusCmd)
}

func runStatus(cmd *cobra.Command, args []string) error {
	// Validate config (skip validation errors for status)
	if cfg.Server.URL == "" {
		return fmt.Errorf("server URL not configured")
	}

	fmt.Println("YouLab Sync Status")
	fmt.Println("==================")
	fmt.Println()

	// Show configuration
	fmt.Printf("Server:       %s\n", cfg.Server.URL)
	fmt.Printf("User ID:      %s\n", maskString(cfg.Server.UserID))
	fmt.Printf("Local Folder: %s\n", cfg.Sync.LocalFolder)
	fmt.Println()

	// Create Ralph client
	client := ralph.NewClient(cfg.Server.URL, cfg.Server.APIKey, cfg.Server.UserID)

	// Check server connection
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	fmt.Print("Checking server connection... ")
	if err := client.Ping(ctx); err != nil {
		fmt.Printf("FAILED (%v)\n", err)
	} else {
		fmt.Println("OK")

		// Get file list if connected
		if cfg.Server.UserID != "" {
			fmt.Print("Getting workspace info... ")
			index, err := client.ListFiles(ctx)
			if err != nil {
				fmt.Printf("FAILED (%v)\n", err)
			} else {
				fmt.Println("OK")
				fmt.Printf("\nWorkspace files: %d\n", len(index.Files))
			}
		}
	}

	return nil
}

func maskString(s string) string {
	if len(s) <= 8 {
		return s
	}
	return s[:4] + "..." + s[len(s)-4:]
}
