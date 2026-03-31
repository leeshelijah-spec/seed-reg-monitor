CREATE TABLE IF NOT EXISTS regulations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    authority TEXT,
    publication_date TEXT,
    effective_date TEXT,
    source_url TEXT NOT NULL,
    summary TEXT,
    amendment_reason TEXT,
    category TEXT NOT NULL DEFAULT '[]',
    department TEXT NOT NULL DEFAULT '[]',
    severity TEXT NOT NULL,
    relevance_reason TEXT,
    severity_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_regulations_source_url
    ON regulations(source_url);

CREATE TABLE IF NOT EXISTS review_logs (
    regulation_id INTEGER NOT NULL,
    reviewer TEXT,
    status TEXT,
    comment TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (regulation_id) REFERENCES regulations(id)
);

CREATE INDEX IF NOT EXISTS idx_review_logs_regulation_id
    ON review_logs(regulation_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    collected_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    message TEXT
);
