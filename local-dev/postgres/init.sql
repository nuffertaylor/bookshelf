-- Enable UUID extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create bookshelf_users table (authentication)
CREATE TABLE IF NOT EXISTS bookshelf_users (
  username VARCHAR(50) PRIMARY KEY,
  hashedPassword VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  authtoken VARCHAR(100) NOT NULL,
  expiry INT NOT NULL,
  salt VARCHAR(100) NOT NULL,
  ip VARCHAR(24),
  banned BOOLEAN NOT NULL,
  goodreads_id TEXT
);

-- Create shelf_images table (generated shelf metadata)
CREATE TABLE IF NOT EXISTS shelf_images (
  shelf_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename TEXT UNIQUE NOT NULL,
  timestamp INT NOT NULL,
  owner TEXT NULL,
  bookshelf_name TEXT NULL,
  gr_shelf_name TEXT NULL,
  gr_user_id TEXT NULL
);

-- Create bookshelf table (book spine uploads)
CREATE TABLE IF NOT EXISTS bookshelf (
  upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id INT NOT NULL,
  title TEXT NOT NULL,
  author TEXT NULL,
  dimensions TEXT NOT NULL,
  domColor TEXT NULL,
  fileName TEXT UNIQUE NOT NULL,
  genre TEXT NULL,
  isbn TEXT NULL,
  isbn13 TEXT NULL,
  pubDate TEXT NULL,
  submitter TEXT NOT NULL,
  rating INT NULL,
  flagged BOOLEAN NULL,
  timestamp INT NULL
);

-- Create visitors table (analytics)
CREATE TABLE IF NOT EXISTS visitors (
  visitor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ip TEXT,
  os TEXT,
  browser TEXT,
  timestamp INT,
  num_visits INT
);

-- Create shelf_bgs table (shelf background configurations)
CREATE TABLE IF NOT EXISTS shelf_bgs (
  bg_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submitter TEXT NOT NULL,
  filename TEXT UNIQUE NOT NULL,
  width_inches INT NOT NULL,
  width_pixels INT NOT NULL,
  shelf_bottoms INT[],
  shelf_left INT,
  timestamp INT,
  title TEXT
);

-- Create unfound_to_upload table (Goodreads books pending upload)
CREATE TABLE IF NOT EXISTS unfound_to_upload (
  upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id INT NOT NULL,
  title TEXT NOT NULL,
  author TEXT NULL,
  isbn TEXT NULL,
  isbn13 TEXT NULL,
  pubDate TEXT NULL,
  owner TEXT NOT NULL,
  uploaded BOOLEAN NULL,
  timestamp INT NULL
);
