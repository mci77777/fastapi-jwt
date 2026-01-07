-- SCHEMA_PART_3.sql
-- Order: 3/5
-- Purpose: Exercise & Workout related tables + their FKs + indexes
-- Run after SCHEMA_PART_2.sql

-- =========================
-- Exercise & Workout tables
-- =========================

-- exercise
CREATE TABLE IF NOT EXISTS exercise (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    muscleGroup TEXT NOT NULL,
    equipment TEXT NOT NULL,
    description TEXT,
    imageUrl TEXT,
    videoUrl TEXT,
    defaultSets BIGINT NOT NULL,
    defaultReps BIGINT NOT NULL,
    defaultWeight DECIMAL(10,2),
    steps TEXT NOT NULL,
    tips TEXT NOT NULL,
    userId BIGINT,
    isCustom BOOLEAN NOT NULL DEFAULT false,
    isFavorite BOOLEAN NOT NULL DEFAULT false,
    difficultyLevel BIGINT NOT NULL,
    calories BIGINT,
    targetMuscles TEXT NOT NULL,
    instructions TEXT NOT NULL,
    embedding TEXT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    createdByUserId TEXT,
    PRIMARY KEY (id)
);

-- exercise_fts
CREATE TABLE IF NOT EXISTS exercise_fts (
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    muscleGroup TEXT NOT NULL,
    equipment TEXT NOT NULL,
    steps TEXT NOT NULL,
    tips TEXT NOT NULL,
    instructions TEXT NOT NULL,
    rowid BIGINT PRIMARY KEY
);

-- exercise_search_history
CREATE TABLE IF NOT EXISTS exercise_search_history (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    resultCount BIGINT NOT NULL,
    userId BIGINT,
    "timestamp" BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- exercise_usage_stats
CREATE TABLE IF NOT EXISTS exercise_usage_stats (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    exerciseId TEXT NOT NULL,
    userId BIGINT,
    usageCount BIGINT NOT NULL,
    lastUsed BIGINT NOT NULL,
    totalSets BIGINT NOT NULL,
    totalReps BIGINT NOT NULL,
    maxWeight DECIMAL(10,2),
    PRIMARY KEY (id)
);

-- workout_plans
CREATE TABLE IF NOT EXISTS workout_plans (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    userId BIGINT NOT NULL,
    targetGoal TEXT,
    difficultyLevel BIGINT NOT NULL,
    estimatedDuration BIGINT,
    isPublic BOOLEAN NOT NULL DEFAULT false,
    isTemplate BOOLEAN NOT NULL DEFAULT false,
    isFavorite BOOLEAN NOT NULL DEFAULT false,
    isAIGenerated BOOLEAN NOT NULL DEFAULT false,
    tags TEXT NOT NULL,
    totalDays BIGINT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- plan_days
CREATE TABLE IF NOT EXISTS plan_days (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    planId UUID NOT NULL,
    dayNumber BIGINT NOT NULL,
    isRestDay BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    orderIndex BIGINT NOT NULL,
    estimatedDuration BIGINT,
    isCompleted BOOLEAN NOT NULL DEFAULT false,
    progress TEXT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- plan_templates
CREATE TABLE IF NOT EXISTS plan_templates (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    planDayId UUID NOT NULL,
    templateId UUID NOT NULL,
    "order" BIGINT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- workout_sessions
CREATE TABLE IF NOT EXISTS workout_sessions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    userId BIGINT NOT NULL,
    templateId TEXT NOT NULL,
    templateVersion BIGINT,
    planId TEXT,
    name VARCHAR(255) NOT NULL,
    "status" TEXT NOT NULL,
    startTime TIMESTAMPTZ NOT NULL,
    endTime TIMESTAMPTZ,
    totalDuration BIGINT,
    totalVolume DECIMAL(10,2),
    caloriesBurned BIGINT,
    notes TEXT,
    rating BIGINT,
    lastAutosaveTime TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id)
);

-- session_exercises
CREATE TABLE IF NOT EXISTS session_exercises (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    sessionId UUID NOT NULL,
    exerciseId TEXT NOT NULL,
    "order" BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    targetSets BIGINT NOT NULL,
    completedSets BIGINT NOT NULL,
    restSeconds BIGINT,
    restSecondsOverride BIGINT,
    imageUrl TEXT,
    videoUrl TEXT,
    "status" TEXT NOT NULL,
    startTime TIMESTAMPTZ,
    endTime TIMESTAMPTZ,
    notes TEXT,
    isCompleted BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (id)
);

-- session_sets
CREATE TABLE IF NOT EXISTS session_sets (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    sessionExerciseId UUID NOT NULL,
    setNumber BIGINT NOT NULL,
    weight DECIMAL(10,2),
    weightUnit TEXT,
    reps BIGINT,
    timeSeconds BIGINT,
    rpe DECIMAL(10,2),
    isCompleted BOOLEAN NOT NULL DEFAULT false,
    isWarmupSet BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    "timestamp" BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- exercise_history_stats
CREATE TABLE IF NOT EXISTS exercise_history_stats (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    userId BIGINT NOT NULL,
    exerciseId TEXT NOT NULL,
    personalBestWeight DECIMAL(10,2),
    personalBestReps BIGINT,
    totalSetsCompleted BIGINT NOT NULL,
    totalVolumeLifted DECIMAL(10,2) NOT NULL,
    lastPerformanceDate BIGINT NOT NULL,
    lastUpdated BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- session_autosave
CREATE TABLE IF NOT EXISTS session_autosave (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    sessionId TEXT NOT NULL,
    saveType TEXT NOT NULL,
    saveTime BIGINT NOT NULL,
    sessionSnapshot TEXT NOT NULL,
    progressSnapshot TEXT NOT NULL,
    currentState TEXT NOT NULL,
    nextAction TEXT NOT NULL,
    isValid BOOLEAN NOT NULL DEFAULT false,
    expiresAt BIGINT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- daily_stats
CREATE TABLE IF NOT EXISTS daily_stats (
    userId BIGINT NOT NULL,
    "date" TEXT NOT NULL,
    completedSessions BIGINT NOT NULL,
    completedExercises BIGINT NOT NULL,
    completedSets BIGINT NOT NULL,
    totalReps BIGINT NOT NULL,
    totalWeight DECIMAL(10,2) NOT NULL,
    avgRpe DECIMAL(10,2),
    sessionDurationSec BIGINT NOT NULL,
    planId TEXT,
    dayOfWeek BIGINT NOT NULL,
    caloriesBurned BIGINT,
    averageHeartRate BIGINT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (userId, "date")
);

-- workout_templates
CREATE TABLE IF NOT EXISTS workout_templates (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    targetMuscleGroups TEXT NOT NULL,
    difficulty BIGINT NOT NULL,
    estimatedDuration BIGINT,
    userId BIGINT NOT NULL,
    isPublic BOOLEAN NOT NULL DEFAULT false,
    isFavorite BOOLEAN NOT NULL DEFAULT false,
    tags TEXT NOT NULL,
    currentVersion BIGINT NOT NULL,
    isDraft BOOLEAN NOT NULL DEFAULT false,
    isPublished BOOLEAN NOT NULL DEFAULT false,
    lastPublishedAt TIMESTAMPTZ,
    versionTag BIGINT NOT NULL,
    jsonData TEXT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- template_exercises
CREATE TABLE IF NOT EXISTS template_exercises (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    templateId UUID NOT NULL,
    exerciseId TEXT NOT NULL,
    "order" BIGINT NOT NULL,
    sets BIGINT NOT NULL,
    repsPerSet TEXT NOT NULL,
    weightSuggestion TEXT,
    restSeconds BIGINT NOT NULL,
    notes TEXT,
    superset BIGINT NOT NULL,
    supersetGroupId TEXT,
    PRIMARY KEY (id)
);

-- template_versions
CREATE TABLE IF NOT EXISTS template_versions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    templateId UUID NOT NULL,
    versionNumber BIGINT NOT NULL,
    contentJson JSONB NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT,
    isAutoSaved BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (id)
);

-- =========================
-- Foreign keys (workout/exercise)
-- =========================
ALTER TABLE plan_days
  ADD CONSTRAINT fk_plan_days_planId
  FOREIGN KEY (planId) REFERENCES workout_plans(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE plan_templates
  ADD CONSTRAINT fk_plan_templates_planDayId
  FOREIGN KEY (planDayId) REFERENCES plan_days(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE session_exercises
  ADD CONSTRAINT fk_session_exercises_sessionId
  FOREIGN KEY (sessionId) REFERENCES workout_sessions(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE session_sets
  ADD CONSTRAINT fk_session_sets_sessionExerciseId
  FOREIGN KEY (sessionExerciseId) REFERENCES session_exercises(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE template_exercises
  ADD CONSTRAINT fk_template_exercises_templateId
  FOREIGN KEY (templateId) REFERENCES workout_templates(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE template_versions
  ADD CONSTRAINT fk_template_versions_templateId
  FOREIGN KEY (templateId) REFERENCES workout_templates(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

-- FKs to user table (existing table with id as primary key)
-- Note: Referencing existing 'user' table with 'id' column, not 'users' table
ALTER TABLE exercise
  ADD CONSTRAINT fk_exercise_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE SET NULL ON UPDATE NO ACTION;

ALTER TABLE exercise_search_history
  ADD CONSTRAINT fk_exercise_search_history_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE SET NULL ON UPDATE NO ACTION;

ALTER TABLE exercise_usage_stats
  ADD CONSTRAINT fk_exercise_usage_stats_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE SET NULL ON UPDATE NO ACTION;

ALTER TABLE workout_plans
  ADD CONSTRAINT fk_workout_plans_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE workout_sessions
  ADD CONSTRAINT fk_workout_sessions_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE exercise_history_stats
  ADD CONSTRAINT fk_exercise_history_stats_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE daily_stats
  ADD CONSTRAINT fk_daily_stats_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE workout_templates
  ADD CONSTRAINT fk_workout_templates_userId
  FOREIGN KEY (userId) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;


-- =========================
-- Indexes (exercise/workout)
-- =========================
CREATE INDEX IF NOT EXISTS idx_exercise_userId ON exercise(userId);
CREATE INDEX IF NOT EXISTS idx_exercise_isFavorite ON exercise(isFavorite);
CREATE INDEX IF NOT EXISTS idx_exercise_createdAt ON exercise(createdAt);
CREATE INDEX IF NOT EXISTS idx_exercise_updatedAt ON exercise(updatedAt);
CREATE INDEX IF NOT EXISTS idx_exercise_search_history_userId ON exercise_search_history(userId);
CREATE INDEX IF NOT EXISTS idx_exercise_usage_stats_userId ON exercise_usage_stats(userId);
CREATE INDEX IF NOT EXISTS idx_workout_plans_userId ON workout_plans(userId);
CREATE INDEX IF NOT EXISTS idx_workout_plans_isPublic ON workout_plans(isPublic);
CREATE INDEX IF NOT EXISTS idx_workout_plans_isFavorite ON workout_plans(isFavorite);
CREATE INDEX IF NOT EXISTS idx_workout_plans_createdAt ON workout_plans(createdAt);
CREATE INDEX IF NOT EXISTS idx_workout_plans_updatedAt ON workout_plans(updatedAt);
CREATE INDEX IF NOT EXISTS idx_plan_days_createdAt ON plan_days(createdAt);
CREATE INDEX IF NOT EXISTS idx_plan_templates_createdAt ON plan_templates(createdAt);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_userId ON workout_sessions(userId);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_status ON workout_sessions("status");
CREATE INDEX IF NOT EXISTS idx_workout_sessions_startTime ON workout_sessions(startTime);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_endTime ON workout_sessions(endTime);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_lastAutosaveTime ON workout_sessions(lastAutosaveTime);
CREATE INDEX IF NOT EXISTS idx_session_exercises_status ON session_exercises("status");
CREATE INDEX IF NOT EXISTS idx_session_exercises_startTime ON session_exercises(startTime);
CREATE INDEX IF NOT EXISTS idx_session_exercises_endTime ON session_exercises(endTime);
CREATE INDEX IF NOT EXISTS idx_exercise_history_stats_userId ON exercise_history_stats(userId);
CREATE INDEX IF NOT EXISTS idx_session_autosave_createdAt ON session_autosave(createdAt);
CREATE INDEX IF NOT EXISTS idx_daily_stats_createdAt ON daily_stats(createdAt);
CREATE INDEX IF NOT EXISTS idx_daily_stats_updatedAt ON daily_stats(updatedAt);
CREATE INDEX IF NOT EXISTS idx_workout_templates_userId ON workout_templates(userId);
CREATE INDEX IF NOT EXISTS idx_workout_templates_isPublic ON workout_templates(isPublic);
CREATE INDEX IF NOT EXISTS idx_workout_templates_isFavorite ON workout_templates(isFavorite);
CREATE INDEX IF NOT EXISTS idx_workout_templates_lastPublishedAt ON workout_templates(lastPublishedAt);
CREATE INDEX IF NOT EXISTS idx_workout_templates_createdAt ON workout_templates(createdAt);
CREATE INDEX IF NOT EXISTS idx_workout_templates_updatedAt ON workout_templates(updatedAt);
CREATE INDEX IF NOT EXISTS idx_template_versions_createdAt ON template_versions(createdAt);

-- =========================
-- Quick verification
-- =========================
SELECT COUNT(*) AS exercise_workout_table_count
FROM information_schema.tables
WHERE table_schema='public' AND table_name IN (
  'exercise','exercise_fts','exercise_search_history','exercise_usage_stats','workout_plans','plan_days',
  'plan_templates','workout_sessions','session_exercises','session_sets','exercise_history_stats','session_autosave',
  'daily_stats','workout_templates','template_exercises','template_versions'
);

