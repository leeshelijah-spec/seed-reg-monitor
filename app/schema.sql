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

CREATE TABLE IF NOT EXISTS news_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    keyword_group TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'seed',
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_news_keywords_unique
    ON news_keywords(keyword, keyword_group);

CREATE INDEX IF NOT EXISTS idx_news_keywords_active
    ON news_keywords(is_active, keyword_group, keyword);

CREATE TABLE IF NOT EXISTS news_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    source_title TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    naver_link TEXT NOT NULL,
    original_link TEXT NOT NULL,
    published_at TEXT,
    collected_at TEXT NOT NULL,
    duplicate_hash TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    topic_category TEXT NOT NULL,
    business_impact_level TEXT NOT NULL,
    urgency_level TEXT NOT NULL,
    relevance_score INTEGER NOT NULL DEFAULT 0,
    recommended_action TEXT NOT NULL,
    owner_department TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT '미검토',
    matched_keywords TEXT NOT NULL DEFAULT '[]',
    analysis_trace TEXT NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_news_articles_duplicate_hash
    ON news_articles(duplicate_hash);

CREATE INDEX IF NOT EXISTS idx_news_articles_published_at
    ON news_articles(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_articles_topic_category
    ON news_articles(topic_category, business_impact_level);

CREATE INDEX IF NOT EXISTS idx_news_articles_owner_department
    ON news_articles(owner_department, urgency_level);

CREATE TABLE IF NOT EXISTS news_collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    run_type TEXT NOT NULL DEFAULT 'scheduled',
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    http_status INTEGER,
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_news_collection_logs_started_at
    ON news_collection_logs(started_at DESC);

CREATE TABLE IF NOT EXISTS news_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL,
    is_relevant INTEGER NOT NULL DEFAULT 0,
    is_noise INTEGER NOT NULL DEFAULT 0,
    impact_level TEXT,
    urgency_level TEXT,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES news_articles(id)
);

CREATE INDEX IF NOT EXISTS idx_news_feedback_article_id
    ON news_feedback(article_id, created_at DESC);
