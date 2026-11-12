-- Local development schema for Postgres 15.
-- Production runs on CockroachDB; STRING → TEXT and gen_random_uuid() work identically.

CREATE TABLE IF NOT EXISTS bookshelf_users (
  username        VARCHAR(50) PRIMARY KEY,
  hashedPassword  VARCHAR(255),
  email           VARCHAR(255) UNIQUE,
  authtoken       VARCHAR(100) NOT NULL,
  expiry          INT NOT NULL,
  salt            VARCHAR(100),
  ip              VARCHAR(24),
  banned          BOOLEAN NOT NULL,
  goodreads_id    TEXT
);

CREATE TABLE IF NOT EXISTS bookshelf (
  upload_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id     INT,
  title       TEXT NOT NULL,
  author      TEXT,
  dimensions  TEXT NOT NULL,
  domColor    TEXT,
  fileName    TEXT UNIQUE NOT NULL,
  genre       TEXT,
  isbn        TEXT,
  isbn13      TEXT,
  pubDate     TEXT,
  submitter   TEXT NOT NULL,
  rating      INT,
  flagged     BOOLEAN,
  timestamp   INT,
  hardcover_book_id INT
);

CREATE TABLE IF NOT EXISTS shelf_images (
  shelf_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename        TEXT UNIQUE NOT NULL,
  timestamp       INT NOT NULL,
  owner           TEXT,
  bookshelf_name  TEXT,
  gr_shelf_name   TEXT,
  gr_user_id      TEXT
);

CREATE TABLE IF NOT EXISTS visitors (
  visitor_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ip          TEXT,
  os          TEXT,
  browser     TEXT,
  timestamp   INT,
  num_visits  INT
);

CREATE TABLE IF NOT EXISTS shelf_bgs (
  bg_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submitter     TEXT NOT NULL,
  filename      TEXT UNIQUE NOT NULL,
  width_inches  INT NOT NULL,
  width_pixels  INT NOT NULL,
  shelf_bottoms INT[],
  shelf_left    INT,
  timestamp     INT,
  title         TEXT
);

CREATE TABLE IF NOT EXISTS unfound_to_upload (
  upload_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id    INT,
  title      TEXT NOT NULL,
  author     TEXT,
  isbn       TEXT,
  isbn13     TEXT,
  pubDate    TEXT,
  owner      TEXT NOT NULL,
  uploaded   BOOLEAN,
  timestamp  INT,
  hardcover_book_id INT
);

-- Hardcover OAuth (plans/02-hardcover-oauth.md; keep in sync with migrations/001_hardcover_oauth.sql).
CREATE TABLE IF NOT EXISTS hardcover_connections (
  username           TEXT PRIMARY KEY REFERENCES bookshelf_users(username),
  hardcover_id       BIGINT UNIQUE NOT NULL,
  hardcover_username TEXT NOT NULL,
  access_token_enc   TEXT NOT NULL,
  refresh_token_enc  TEXT NOT NULL,
  access_expires_at  INT NOT NULL,
  scopes             TEXT NOT NULL,
  needs_reauth       BOOLEAN NOT NULL DEFAULT false,
  created_at         INT NOT NULL,
  updated_at         INT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_states (
  state         TEXT PRIMARY KEY,
  code_verifier TEXT NOT NULL,
  mode          TEXT NOT NULL,
  username      TEXT,
  created_at    INT NOT NULL,
  expires_at    INT NOT NULL,
  used          BOOLEAN NOT NULL DEFAULT false
);

-- Indexes for getGRBookshelf: batch lookup by normalised title+author and by book_id.
CREATE INDEX IF NOT EXISTS idx_bookshelf_title_author
  ON bookshelf (LOWER(TRIM(title)), LOWER(TRIM(author)));

CREATE INDEX IF NOT EXISTS idx_bookshelf_book_id
  ON bookshelf (book_id);

CREATE INDEX IF NOT EXISTS bookshelf_hardcover_book_id_idx
  ON bookshelf (hardcover_book_id);

-- Useful for getSpinesBySubmitter and leaderboard.
CREATE INDEX IF NOT EXISTS idx_bookshelf_submitter
  ON bookshelf (submitter);

-- Useful for getOwnerShelves.
CREATE INDEX IF NOT EXISTS idx_shelf_images_owner
  ON shelf_images (owner);

-- Useful for getUnfoundToUpload.
CREATE INDEX IF NOT EXISTS idx_unfound_owner_uploaded
  ON unfound_to_upload (owner, uploaded);
