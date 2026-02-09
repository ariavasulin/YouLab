package config

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// Config represents the application configuration
type Config struct {
	Server  ServerConfig  `yaml:"server"`
	Sync    SyncConfig    `yaml:"sync"`
	Watch   WatchConfig   `yaml:"watch"`
	Ignore  []string      `yaml:"ignore"`
	Logging LoggingConfig `yaml:"logging"`
}

// ServerConfig defines Ralph server connection settings
type ServerConfig struct {
	URL    string `yaml:"url"`
	APIKey string `yaml:"api_key"`
	UserID string `yaml:"user_id"`
}

// SyncConfig defines synchronization settings
type SyncConfig struct {
	LocalFolder   string        `yaml:"local_folder"`
	Interval      time.Duration `yaml:"interval"`
	Bidirectional bool          `yaml:"bidirectional"`
}

// WatchConfig defines file watching settings
type WatchConfig struct {
	Enabled  bool          `yaml:"enabled"`
	Debounce time.Duration `yaml:"debounce"`
}

// LoggingConfig defines logging settings
type LoggingConfig struct {
	Level string `yaml:"level"`
	File  string `yaml:"file"`
}

// DefaultConfig returns a configuration with sensible defaults
func DefaultConfig() *Config {
	return &Config{
		Server: ServerConfig{
			URL:    getEnv("YOULAB_SERVER_URL", "http://localhost:8200"),
			APIKey: getEnv("YOULAB_API_KEY", ""),
			UserID: getEnv("YOULAB_USER_ID", ""),
		},
		Sync: SyncConfig{
			LocalFolder:   getEnv("YOULAB_LOCAL_FOLDER", ""),
			Interval:      30 * time.Second,
			Bidirectional: true,
		},
		Watch: WatchConfig{
			Enabled:  true,
			Debounce: 500 * time.Millisecond,
		},
		Ignore: []string{
			".git",
			".DS_Store",
			"*.tmp",
			"*.temp",
			"*.swp",
			"*.swo",
			"node_modules",
			"__pycache__",
			".pytest_cache",
			"*.log",
			"Thumbs.db",
			"desktop.ini",
		},
		Logging: LoggingConfig{
			Level: "info",
			File:  "",
		},
	}
}

// Load loads configuration from file, merging with defaults and environment variables
func Load(path string) (*Config, error) {
	cfg := DefaultConfig()

	// Load from file if it exists
	if _, err := os.Stat(path); err == nil {
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}

		if err := yaml.Unmarshal(data, cfg); err != nil {
			return nil, fmt.Errorf("failed to parse config file: %w", err)
		}
	}

	// Override with environment variables
	if url := os.Getenv("YOULAB_SERVER_URL"); url != "" {
		cfg.Server.URL = url
	}
	if apiKey := os.Getenv("YOULAB_API_KEY"); apiKey != "" {
		cfg.Server.APIKey = apiKey
	}
	if userID := os.Getenv("YOULAB_USER_ID"); userID != "" {
		cfg.Server.UserID = userID
	}
	if folder := os.Getenv("YOULAB_LOCAL_FOLDER"); folder != "" {
		cfg.Sync.LocalFolder = folder
	}

	return cfg, nil
}

// Validate checks if the configuration is valid
func (c *Config) Validate() error {
	if c.Server.URL == "" {
		return fmt.Errorf("server URL is required")
	}
	if c.Server.UserID == "" {
		return fmt.Errorf("user ID is required")
	}
	if c.Sync.LocalFolder == "" {
		return fmt.Errorf("local folder is required")
	}

	// Check if local folder exists
	if _, err := os.Stat(c.Sync.LocalFolder); os.IsNotExist(err) {
		return fmt.Errorf("local folder does not exist: %s", c.Sync.LocalFolder)
	}

	return nil
}

// Save writes the configuration to a file
func (c *Config) Save(path string) error {
	data, err := yaml.Marshal(c)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("failed to write config file: %w", err)
	}

	return nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
