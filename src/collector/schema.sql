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

-- S7: the prompts file of each helper version, as JSON text, written once by the first upload that carries it. Its
-- version ends in the hash of its components, which the Worker checks, so no later upload can change it.
CREATE TABLE IF NOT EXISTS prompts (
  version TEXT PRIMARY KEY,
  prompts TEXT NOT NULL,
  received_at TEXT NOT NULL
);

-- S8: feedback on the method from the web app, one row per item: kind `flag` (a flag marked unfair and its rule) or
-- `prompt` (a comment on a part, a rule or a quoted span of a prompts version). Only the owner reads it. The daily
-- stops count these rows.
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  video_id TEXT,
  flag_id TEXT,
  rule TEXT,
  version TEXT,
  component TEXT,
  quote TEXT,
  text TEXT NOT NULL,
  install_id TEXT NOT NULL,
  received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_received_at ON feedback (received_at);
CREATE INDEX IF NOT EXISTS feedback_install_id ON feedback (install_id, received_at);

-- S5: the flags the owner hid, by video, language and flag id: never served and counted nowhere. One row covers the
-- pending upload and the approved one, and outlives a re-upload. Nothing is deleted from the analysis.
CREATE TABLE IF NOT EXISTS hidden (
  video_id TEXT NOT NULL,
  lang TEXT NOT NULL,
  flag_id TEXT NOT NULL,
  hidden_at TEXT NOT NULL,
  PRIMARY KEY (video_id, lang, flag_id)
);

-- S7 of the web RFC: visits of a video page and jumps to a flag's moment, summed per video, language, UTC day and kind
-- ("visit" or "seek"). No cookie, no install id: nothing tells one person from another.
CREATE TABLE IF NOT EXISTS visits (
  video_id TEXT NOT NULL,
  lang TEXT NOT NULL,
  day TEXT NOT NULL,
  kind TEXT NOT NULL,
  n INTEGER NOT NULL,
  PRIMARY KEY (video_id, lang, day, kind)
);

-- S11: the debates whose thumbnail shows the guests the other way round, one row per video for every language, set
-- by the owner's switch on the review page. No row: the first guest of `guests` is the left half, the second the right.
CREATE TABLE IF NOT EXISTS faces (
  video_id TEXT PRIMARY KEY,
  swapped_at TEXT NOT NULL
);

-- The owner's display title of a video (2026-11-22): it wins over the clean title computed from the raw one, for the
-- cases the casing rule gets wrong. One row per video; deleting it gives the clean title back.
CREATE TABLE IF NOT EXISTS titles (
  video_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  set_at TEXT NOT NULL
);

-- The videos the owner turned off (2026-11-22): the public API, the web app's share tags and the visit counter skip
-- them, and the review page still lists them. One row per video for every language; deleting it turns the video on.
CREATE TABLE IF NOT EXISTS inactive (
  video_id TEXT PRIMARY KEY,
  off_at TEXT NOT NULL
);
