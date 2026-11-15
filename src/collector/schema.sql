-- The feedback collector's D1 tables. Apply once: npx wrangler d1 execute fact-checker-feedback --remote --file=schema.sql

-- One row per tester, video and flag: a mark sent again replaces its row.
CREATE TABLE IF NOT EXISTS marks (
  install_id TEXT NOT NULL,
  video_id TEXT NOT NULL,
  flag_id TEXT NOT NULL,
  t REAL NOT NULL,
  type TEXT NOT NULL,
  label TEXT NOT NULL,
  quote TEXT NOT NULL,
  confidence REAL NOT NULL,
  verdict TEXT NOT NULL,
  reason TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  helper_version TEXT NOT NULL,
  received_at TEXT NOT NULL,
  PRIMARY KEY (install_id, video_id, flag_id)
);
CREATE INDEX IF NOT EXISTS marks_received_at ON marks (received_at);

-- The accepted requests of each tester per UTC day: the hard stop.
CREATE TABLE IF NOT EXISTS requests (
  install_id TEXT NOT NULL,
  day TEXT NOT NULL,
  n INTEGER NOT NULL,
  PRIMARY KEY (install_id, day)
);

-- S28: one shared analysis per video and language, the stripped flag file as JSON text (under D1's 2 MB row limit).
-- `rank` is the place of `model` (the parts model) in the Worker's RANK list, -1 for any other.
CREATE TABLE IF NOT EXISTS analyses (
  video_id TEXT NOT NULL,
  lang TEXT NOT NULL,
  analysis TEXT NOT NULL,
  model TEXT,
  rank INTEGER NOT NULL,
  install_id TEXT NOT NULL,
  received_at TEXT NOT NULL,
  PRIMARY KEY (video_id, lang)
);

-- The accepted analysis uploads of each tester per UTC day: their hard stop.
CREATE TABLE IF NOT EXISTS uploads (
  install_id TEXT NOT NULL,
  day TEXT NOT NULL,
  n INTEGER NOT NULL,
  PRIMARY KEY (install_id, day)
);

-- S30: an upload without the owner's token waits here, one row per video, language and uploader, until the owner
-- approves it into `analyses` (the only table served) or rejects it. `rank` as in `analyses`.
CREATE TABLE IF NOT EXISTS pending (
  video_id TEXT NOT NULL,
  lang TEXT NOT NULL,
  install_id TEXT NOT NULL,
  analysis TEXT NOT NULL,
  model TEXT,
  rank INTEGER NOT NULL,
  received_at TEXT NOT NULL,
  PRIMARY KEY (video_id, lang, install_id)
);

-- One-time steps already applied, so this file stays safe to apply again.
CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY);

-- S30: the analyses served before the review wait for the owner's approval, once.
INSERT OR IGNORE INTO pending (video_id, lang, install_id, analysis, model, rank, received_at)
  SELECT video_id, lang, install_id, analysis, model, rank, received_at FROM analyses
  WHERE NOT EXISTS (SELECT 1 FROM migrations WHERE name = 's30-review');
DELETE FROM analyses WHERE NOT EXISTS (SELECT 1 FROM migrations WHERE name = 's30-review');
INSERT OR IGNORE INTO migrations (name) VALUES ('s30-review');
