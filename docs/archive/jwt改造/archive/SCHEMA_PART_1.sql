-- SCHEMA_PART_1.sql
-- Order: 1/5
-- Purpose: Extensions + Core tables (users, user_profiles, user_settings, tokens) + their indexes + direct FKs
-- Run this first in Supabase SQL Editor.

-- Extensions (required for UUID generation and scheduling)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_cron";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- Compatibility patch: Use existing public.user table (note: singular 'user', not 'users')
-- The existing user table has 'id' as primary key (bigint), which will be referenced by foreign keys
-- No modifications needed to existing user table structure

-- =========================
-- Core tables
-- =========================

-- Note: Using existing 'user' table instead of creating new 'users' table
-- The existing user table structure:
-- - Primary key: id (bigint)
-- - Has columns: name, email, emailVerified, image, createdAt, updatedAt, phoneNumber, phoneNumberVerified
-- Additional GymBro-specific columns will be added to user_profiles table instead

-- user_profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    userId BIGINT NOT NULL,
    username VARCHAR(255),
    displayName VARCHAR(255),
    email VARCHAR(255),
    phoneNumber TEXT,
    profileImageUrl TEXT,
    bio TEXT,
    gender TEXT,
    height DECIMAL(10,2),
    heightUnit TEXT,
    weight DECIMAL(10,2),
    weightUnit TEXT,
    fitnessLevel BIGINT,
    fitnessGoals TEXT NOT NULL,
    workoutDays TEXT NOT NULL,
    allowPartnerMatching BIGINT NOT NULL,
    totalWorkoutCount BIGINT NOT NULL,
    weeklyActiveMinutes BIGINT NOT NULL,
    likesReceived BIGINT NOT NULL,
    isAnonymous BOOLEAN NOT NULL DEFAULT false,
    hasValidSubscription BIGINT NOT NULL,
    lastUpdated BIGINT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profileSummary TEXT,
    vector BYTEA,
    vectorCreatedAt BIGINT,
    PRIMARY KEY (userId)
);

-- user_settings
CREATE TABLE IF NOT EXISTS user_settings (
    userId BIGINT NOT NULL,
    themeMode TEXT NOT NULL,
    languageCode TEXT NOT NULL,
    measurementSystem TEXT NOT NULL,
    notificationsEnabled BOOLEAN NOT NULL DEFAULT false,
    soundsEnabled BOOLEAN NOT NULL DEFAULT false,
    locationSharingEnabled BOOLEAN NOT NULL DEFAULT false,
    dataSharingEnabled BOOLEAN NOT NULL DEFAULT false,
    allowWorkoutSharing BIGINT NOT NULL,
    autoBackupEnabled BOOLEAN NOT NULL DEFAULT false,
    backupFrequency BIGINT NOT NULL,
    lastBackupTime BIGINT NOT NULL,
    allowPartnerMatching BIGINT NOT NULL,
    preferredMatchDistance BOOLEAN NOT NULL DEFAULT false,
    matchByFitnessLevel BIGINT NOT NULL,
    lastModified TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (userId)
);

-- tokens
CREATE TABLE IF NOT EXISTS tokens (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    accessToken TEXT NOT NULL,
    refreshToken TEXT NOT NULL,
    tokenType TEXT NOT NULL,
    expiresIn BIGINT NOT NULL,
    issuedAt BOOLEAN NOT NULL DEFAULT false,
    userId BIGINT NOT NULL,
    scope TEXT,
    PRIMARY KEY (id)
);

-- =========================
-- Foreign keys (within this part)
-- =========================
-- Note: Referencing existing 'user' table with 'id' column, not 'users' table
-- The userId columns in these tables should reference the existing user.id
ALTER TABLE user_settings
  ADD CONSTRAINT fk_user_settings_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE CASCADE ON UPDATE NO ACTION;

ALTER TABLE user_profiles
  ADD CONSTRAINT fk_user_profiles_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE CASCADE ON UPDATE NO ACTION;

ALTER TABLE tokens
  ADD CONSTRAINT fk_tokens_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE CASCADE ON UPDATE NO ACTION;

-- =========================
-- Indexes (core tables)
-- =========================
-- Note: Not creating indexes on existing 'user' table to avoid conflicts
-- Only creating indexes on new tables
CREATE INDEX IF NOT EXISTS idx_user_profiles_createdAt ON user_profiles(createdAt);
CREATE INDEX IF NOT EXISTS idx_user_settings_lastModified ON user_settings(lastModified);
CREATE INDEX IF NOT EXISTS idx_tokens_userId ON tokens(userId);

-- =========================
-- Quick verification
-- =========================
-- Expect 4 core tables to exist (including existing 'user' table)
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_name IN ('user','user_profiles','user_settings','tokens')
ORDER BY table_name;
