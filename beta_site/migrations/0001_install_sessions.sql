CREATE TABLE install_sessions (
  id TEXT PRIMARY KEY,
  downloaded_at TEXT NOT NULL,
  confirmed_at TEXT
);

CREATE INDEX install_sessions_confirmed_at_idx
  ON install_sessions (confirmed_at);
