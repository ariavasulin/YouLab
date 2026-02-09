package ralph

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// Client provides methods to interact with the Ralph workspace API
type Client struct {
	baseURL    string
	apiKey     string
	userID     string
	httpClient *http.Client
}

// FileMetadata represents metadata for a file in the workspace
type FileMetadata struct {
	Path     string    `json:"path"`
	Hash     string    `json:"hash"`
	Size     int64     `json:"size"`
	Modified time.Time `json:"modified"`
}

// WorkspaceIndex represents the list of files in a workspace
type WorkspaceIndex struct {
	UserID string                  `json:"user_id"`
	Files  map[string]FileMetadata `json:"files"`
}

// SyncDirection indicates the direction of sync
type SyncDirection string

const (
	SyncToOpenWebUI   SyncDirection = "to_openwebui"
	SyncFromOpenWebUI SyncDirection = "from_openwebui"
	SyncBidirectional SyncDirection = "bidirectional"
)

// NewClient creates a new Ralph API client
func NewClient(baseURL, apiKey, userID string) *Client {
	return &Client{
		baseURL: baseURL,
		apiKey:  apiKey,
		userID:  userID,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// ListFiles retrieves the list of files in the user's workspace
func (c *Client) ListFiles(ctx context.Context) (*WorkspaceIndex, error) {
	endpoint := fmt.Sprintf("%s/users/%s/workspace/files", c.baseURL, c.userID)

	req, err := http.NewRequestWithContext(ctx, "GET", endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	c.setHeaders(req)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var index WorkspaceIndex
	if err := json.NewDecoder(resp.Body).Decode(&index); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &index, nil
}

// GetFile downloads a file from the workspace
func (c *Client) GetFile(ctx context.Context, path string) ([]byte, *FileMetadata, error) {
	endpoint := fmt.Sprintf("%s/users/%s/workspace/files/%s", c.baseURL, c.userID, url.PathEscape(path))

	req, err := http.NewRequestWithContext(ctx, "GET", endpoint, nil)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to create request: %w", err)
	}

	c.setHeaders(req)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, nil, nil // File doesn't exist
	}

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	content, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to read response body: %w", err)
	}

	// Parse metadata from headers
	metadata := &FileMetadata{
		Path: path,
	}

	if hash := resp.Header.Get("X-File-Hash"); hash != "" {
		metadata.Hash = hash
	}

	if modified := resp.Header.Get("X-File-Modified"); modified != "" {
		if t, err := time.Parse(time.RFC3339, modified); err == nil {
			metadata.Modified = t
		}
	}

	metadata.Size = int64(len(content))

	return content, metadata, nil
}

// PutFile uploads or updates a file in the workspace
func (c *Client) PutFile(ctx context.Context, path string, content []byte) (*FileMetadata, error) {
	endpoint := fmt.Sprintf("%s/users/%s/workspace/files/%s", c.baseURL, c.userID, url.PathEscape(path))

	req, err := http.NewRequestWithContext(ctx, "PUT", endpoint, bytes.NewReader(content))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	c.setHeaders(req)
	req.Header.Set("Content-Type", "application/octet-stream")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var metadata FileMetadata
	if err := json.NewDecoder(resp.Body).Decode(&metadata); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &metadata, nil
}

// DeleteFile removes a file from the workspace
func (c *Client) DeleteFile(ctx context.Context, path string) error {
	endpoint := fmt.Sprintf("%s/users/%s/workspace/files/%s", c.baseURL, c.userID, url.PathEscape(path))

	req, err := http.NewRequestWithContext(ctx, "DELETE", endpoint, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	c.setHeaders(req)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

// TriggerSync triggers a sync operation on the server
func (c *Client) TriggerSync(ctx context.Context, direction SyncDirection) error {
	endpoint := fmt.Sprintf("%s/users/%s/workspace/sync", c.baseURL, c.userID)

	body := struct {
		Direction string `json:"direction"`
	}{
		Direction: string(direction),
	}

	jsonBody, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("failed to marshal request body: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", endpoint, bytes.NewReader(jsonBody))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	c.setHeaders(req)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// Ping checks if the server is reachable
func (c *Client) Ping(ctx context.Context) error {
	endpoint := fmt.Sprintf("%s/health", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, "GET", endpoint, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("server returned status %d", resp.StatusCode)
	}

	return nil
}

func (c *Client) setHeaders(req *http.Request) {
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	req.Header.Set("User-Agent", "youlab-sync/1.0")
}
