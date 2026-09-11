CREATE TABLE recordings (
    id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    transcript LONGTEXT NULL,
    summary_result JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX ix_recordings_created (created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tasks (
    id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    recording_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    status ENUM('pending', 'transcribing', 'summarizing', 'done', 'failed') NOT NULL DEFAULT 'pending',
    attempt INT UNSIGNED NOT NULL DEFAULT 1,
    error_code VARCHAR(64) NULL,
    error_message TEXT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    started_at DATETIME(6) NULL,
    finished_at DATETIME(6) NULL,
    UNIQUE KEY uq_tasks_recording (recording_id),
    INDEX ix_tasks_status_created (status, created_at),
    CONSTRAINT fk_tasks_recording FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
