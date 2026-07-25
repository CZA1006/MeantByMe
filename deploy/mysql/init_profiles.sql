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
