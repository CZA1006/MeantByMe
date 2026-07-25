CREATE DATABASE IF NOT EXISTS meantbyme
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE meantbyme;

CREATE TABLE IF NOT EXISTS user_profiles (
    profile_ref VARCHAR(160) NOT NULL PRIMARY KEY,
    profile_id VARCHAR(80) NOT NULL,
    markdown MEDIUMTEXT NOT NULL,
    source ENUM('questionnaire', 'uploaded') NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_user_profiles_created (created_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS expression_mappings (
    mapping_id VARCHAR(160) NOT NULL PRIMARY KEY,
    profile_ref VARCHAR(160) NOT NULL,
    profile_id VARCHAR(80) NOT NULL,
    input_text TEXT NOT NULL,
    intent_text TEXT NOT NULL,
    language VARCHAR(12) NOT NULL,
    embedding TEXT NOT NULL,
    confidence DOUBLE NOT NULL,
    positive_count INT NOT NULL DEFAULT 0,
    negative_count INT NOT NULL DEFAULT 0,
    last_session_id VARCHAR(160) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    INDEX idx_expression_mapping_scope(
        profile_ref, profile_id, confidence, updated_at
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS expression_feedback_events (
    feedback_key VARCHAR(160) NOT NULL PRIMARY KEY,
    mapping_id VARCHAR(160) NOT NULL,
    profile_ref VARCHAR(160) NOT NULL,
    profile_id VARCHAR(80) NOT NULL,
    session_id VARCHAR(160) NOT NULL,
    confirmed TINYINT(1) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX idx_expression_feedback_scope(profile_ref, profile_id, created_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
