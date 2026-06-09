CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    domain TEXT DEFAULT 'personal',
    due_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    is_done BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notes_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    chunk_count INTEGER,
    content_hash TEXT
);
