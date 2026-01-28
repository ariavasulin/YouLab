-- Create the YouLab database
CREATE DATABASE IF NOT EXISTS youlab;
USE youlab;

-- Memory blocks table
-- Primary key (user_id, label) enables cell-wise versioning in Dolt
CREATE TABLE IF NOT EXISTS memory_blocks (
    user_id VARCHAR(255) NOT NULL COMMENT 'OpenWebUI user ID',
    label VARCHAR(100) NOT NULL COMMENT 'Block identifier (e.g., student, journey)',
    title VARCHAR(255) COMMENT 'Human-readable block title',
    body TEXT COMMENT 'Block content (markdown)',
    schema_ref VARCHAR(255) COMMENT 'Schema reference (e.g., college-essay/student)',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Initial commit
CALL DOLT_ADD('-A');
CALL DOLT_COMMIT('-m', 'Initial schema setup');
