ALTER TABLE install_sessions
  ADD COLUMN release_version TEXT NOT NULL DEFAULT 'legacy';

CREATE INDEX install_sessions_release_version_downloaded_at_idx
  ON install_sessions (release_version, downloaded_at);
