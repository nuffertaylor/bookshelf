-- 001: Hardcover OAuth sign-in (plans/02-hardcover-oauth.md, section 5).
--
-- Run BY HAND against prod CockroachDB, and against a local Postgres created before this change.
-- Fresh local databases get the same result from local-dev/migrate.sql.
--
-- Every statement is safe to run on its own (idempotent) and none depends on a transaction. Run
-- them one at a time, OUTSIDE an explicit BEGIN/COMMIT: CockroachDB limits schema changes inside
-- transactions. Types are TEXT/INT so the file works unchanged on Postgres and CockroachDB.

-- 5.1 bookshelf_users: allow accounts with no password or email (a "legacy" account is one with
-- hashedPassword IS NOT NULL). email stays UNIQUE; NULLs do not collide.
ALTER TABLE bookshelf_users ALTER COLUMN hashedPassword DROP NOT NULL;
ALTER TABLE bookshelf_users ALTER COLUMN salt DROP NOT NULL;
ALTER TABLE bookshelf_users ALTER COLUMN email DROP NOT NULL;

-- 5.2 One row per linked Hardcover account. Tokens are KMS-encrypted by the application.
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

-- 5.3 Pending OAuth authorizations (state + PKCE verifier).
CREATE TABLE IF NOT EXISTS oauth_states (
  state         TEXT PRIMARY KEY,
  code_verifier TEXT NOT NULL,
  mode          TEXT NOT NULL,
  username      TEXT NULL,
  created_at    INT NOT NULL,
  expires_at    INT NOT NULL,
  used          BOOLEAN NOT NULL DEFAULT false
);

-- 5.4 Hardcover book ids on spines and the upload queue. The new column is appended LAST, so the
-- positional SELECT * mapping in the DAO (format_book_tuple: index 15, format_unfound_to_upload_tuple:
-- index 10) stays correct. Verify with: SELECT * FROM bookshelf LIMIT 1;
ALTER TABLE bookshelf ADD COLUMN IF NOT EXISTS hardcover_book_id INT NULL;
ALTER TABLE bookshelf ALTER COLUMN book_id DROP NOT NULL;
CREATE INDEX IF NOT EXISTS bookshelf_hardcover_book_id_idx ON bookshelf (hardcover_book_id);

ALTER TABLE unfound_to_upload ADD COLUMN IF NOT EXISTS hardcover_book_id INT NULL;
ALTER TABLE unfound_to_upload ALTER COLUMN book_id DROP NOT NULL;
