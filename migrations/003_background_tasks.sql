-- Background task definitions
CREATE TABLE IF NOT EXISTS background_tasks (
    name VARCHAR(255) PRIMARY KEY,
    system_prompt TEXT NOT NULL,
    tools JSON NOT NULL,  -- ["query_honcho", "edit_memory_block"]
    memory_blocks JSON NOT NULL,  -- ["student", "progress"]
    trigger_type ENUM('cron', 'idle') NOT NULL,
    trigger_config JSON NOT NULL,  -- {"schedule": "0 3 * * *"} or {"idle_minutes": 30, "cooldown_minutes": 60}
    user_ids JSON NOT NULL,  -- ["user-1", "user-2"]
    batch_size INT DEFAULT 5,
    max_turns INT DEFAULT 10,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Task execution history
CREATE TABLE IF NOT EXISTS task_runs (
    id VARCHAR(36) PRIMARY KEY,  -- UUID
    task_name VARCHAR(255) NOT NULL,
    trigger_type ENUM('cron', 'idle') NOT NULL,
    status ENUM('pending', 'running', 'success', 'failed', 'partial') NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NULL,
    user_results JSON NULL,  -- Array of UserRunResult
    error TEXT NULL,
    FOREIGN KEY (task_name) REFERENCES background_tasks(name) ON DELETE CASCADE,
    INDEX idx_task_runs_task_name (task_name),
    INDEX idx_task_runs_started_at (started_at)
);

-- User activity tracking for idle triggers
CREATE TABLE IF NOT EXISTS user_activity (
    user_id VARCHAR(255) PRIMARY KEY,
    last_message_at TIMESTAMP NOT NULL,
    last_task_runs JSON DEFAULT '{}',  -- {"task_name": "2024-01-28T12:00:00Z"}
    INDEX idx_user_activity_last_message (last_message_at)
);
