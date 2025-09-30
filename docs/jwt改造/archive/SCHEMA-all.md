-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.calendar_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL,
  workout_id text,
  event_type text NOT NULL,
  date bigint NOT NULL,
  title character varying NOT NULL,
  description text,
  duration_minutes bigint,
  color text,
  is_all_day boolean NOT NULL DEFAULT false,
  reminder_minutes_before bigint,
  is_completed boolean NOT NULL DEFAULT false,
  completion_date bigint,
  cancelled bigint NOT NULL,
  recurrence_rule text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  modified_at bigint NOT NULL,
  is_synced boolean NOT NULL DEFAULT false,
  CONSTRAINT calendar_events_pkey PRIMARY KEY (id),
  CONSTRAINT fk_calendar_events_user_id FOREIGN KEY (user_id) REFERENCES public.user(id)
);
CREATE TABLE public.chat_fts (
  content text NOT NULL,
  rowid bigint NOT NULL,
  CONSTRAINT chat_fts_pkey PRIMARY KEY (rowid)
);
CREATE TABLE public.chat_raw (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  role text NOT NULL,
  content text NOT NULL,
  timestamp bigint NOT NULL,
  metadata text NOT NULL,
  message_id text NOT NULL,
  in_reply_to_message_id text,
  thinking_nodes text,
  final_markdown text,
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT chat_raw_pkey PRIMARY KEY (id),
  CONSTRAINT fk_chat_raw_session_id FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id)
);
CREATE TABLE public.chat_sessions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  title character varying NOT NULL,
  user_id bigint NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  last_active_at bigint NOT NULL,
  is_active boolean NOT NULL DEFAULT false,
  status bigint NOT NULL,
  message_count bigint NOT NULL,
  summary text,
  metadata text,
  db_created_at bigint NOT NULL,
  db_updated_at bigint NOT NULL,
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT chat_sessions_pkey PRIMARY KEY (id),
  CONSTRAINT fk_chat_sessions_user_id FOREIGN KEY (user_id) REFERENCES public.user(id)
);
CREATE TABLE public.chat_vec (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  embedding bytea NOT NULL,
  embedding_dim bigint NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT chat_vec_pkey PRIMARY KEY (id)
);
CREATE TABLE public.daily_stats (
  userid bigint NOT NULL,
  date text NOT NULL,
  completedsessions bigint NOT NULL,
  completedexercises bigint NOT NULL,
  completedsets bigint NOT NULL,
  totalreps bigint NOT NULL,
  totalweight numeric NOT NULL,
  avgrpe numeric,
  sessiondurationsec bigint NOT NULL,
  planid text,
  dayofweek bigint NOT NULL,
  caloriesburned bigint,
  averageheartrate bigint,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  updatedat timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT daily_stats_pkey PRIMARY KEY (date, userid),
  CONSTRAINT fk_daily_stats_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.exercise (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name character varying NOT NULL,
  musclegroup text NOT NULL,
  equipment text NOT NULL,
  description text,
  imageurl text,
  videourl text,
  defaultsets bigint NOT NULL,
  defaultreps bigint NOT NULL,
  defaultweight numeric,
  steps text NOT NULL,
  tips text NOT NULL,
  userid bigint,
  iscustom boolean NOT NULL DEFAULT false,
  isfavorite boolean NOT NULL DEFAULT false,
  difficultylevel bigint NOT NULL,
  calories bigint,
  targetmuscles text NOT NULL,
  instructions text NOT NULL,
  embedding text,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  updatedat timestamp with time zone NOT NULL DEFAULT now(),
  createdbyuserid text,
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT exercise_pkey PRIMARY KEY (id),
  CONSTRAINT fk_exercise_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.exercise_fts (
  name character varying NOT NULL,
  description text NOT NULL,
  musclegroup text NOT NULL,
  equipment text NOT NULL,
  steps text NOT NULL,
  tips text NOT NULL,
  instructions text NOT NULL,
  rowid bigint NOT NULL,
  CONSTRAINT exercise_fts_pkey PRIMARY KEY (rowid)
);
CREATE TABLE public.exercise_history_stats (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  userid bigint NOT NULL,
  exerciseid text NOT NULL,
  personalbestweight numeric,
  personalbestreps bigint,
  totalsetscompleted bigint NOT NULL,
  totalvolumelifted numeric NOT NULL,
  lastperformancedate bigint NOT NULL,
  lastupdated bigint NOT NULL,
  CONSTRAINT exercise_history_stats_pkey PRIMARY KEY (id),
  CONSTRAINT fk_exercise_history_stats_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.exercise_search_history (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  query text NOT NULL,
  resultcount bigint NOT NULL,
  userid bigint,
  timestamp bigint NOT NULL,
  CONSTRAINT exercise_search_history_pkey PRIMARY KEY (id),
  CONSTRAINT fk_exercise_search_history_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.exercise_usage_stats (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  exerciseid text NOT NULL,
  userid bigint,
  usagecount bigint NOT NULL,
  lastused bigint NOT NULL,
  totalsets bigint NOT NULL,
  totalreps bigint NOT NULL,
  maxweight numeric,
  CONSTRAINT exercise_usage_stats_pkey PRIMARY KEY (id),
  CONSTRAINT fk_exercise_usage_stats_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.memory_records (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL,
  tier text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  expires_at bigint,
  importance bigint NOT NULL,
  embedding bytea,
  embedding_dim bigint NOT NULL,
  embedding_status text NOT NULL,
  payload_json jsonb NOT NULL,
  content_length bigint NOT NULL,
  model_version text NOT NULL,
  generation_time_ms bigint,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT memory_records_pkey PRIMARY KEY (id),
  CONSTRAINT fk_memory_records_user_id FOREIGN KEY (user_id) REFERENCES public.user(id)
);
CREATE TABLE public.message_embedding (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  message_id uuid NOT NULL,
  vector bytea NOT NULL,
  vector_dim bigint NOT NULL,
  embedding_status text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  model_version text NOT NULL,
  generation_time_ms bigint,
  text_length bigint NOT NULL,
  CONSTRAINT message_embedding_pkey PRIMARY KEY (id),
  CONSTRAINT fk_message_embedding_message_id FOREIGN KEY (message_id) REFERENCES public.chat_raw(id)
);
CREATE TABLE public.plan_days (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  planid uuid NOT NULL,
  daynumber bigint NOT NULL,
  isrestday boolean NOT NULL DEFAULT false,
  notes text,
  orderindex bigint NOT NULL,
  estimatedduration bigint,
  iscompleted boolean NOT NULL DEFAULT false,
  progress text NOT NULL,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT plan_days_pkey PRIMARY KEY (id),
  CONSTRAINT fk_plan_days_planid FOREIGN KEY (planid) REFERENCES public.workout_plans(id)
);
CREATE TABLE public.plan_templates (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  plandayid uuid NOT NULL,
  templateid uuid NOT NULL,
  order bigint NOT NULL,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT plan_templates_pkey PRIMARY KEY (id),
  CONSTRAINT fk_plan_templates_plandayid FOREIGN KEY (plandayid) REFERENCES public.plan_days(id)
);
CREATE TABLE public.public_shares (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL,
  user_id text NOT NULL,
  share_token character varying NOT NULL UNIQUE,
  title text,
  description text,
  is_public boolean DEFAULT true,
  expires_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT public_shares_pkey PRIMARY KEY (id)
);
CREATE TABLE public.search_content (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  content text NOT NULL,
  embedding text,
  metadata text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT search_content_pkey PRIMARY KEY (id)
);
CREATE TABLE public.session_autosave (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  sessionid text NOT NULL,
  savetype text NOT NULL,
  savetime bigint NOT NULL,
  sessionsnapshot text NOT NULL,
  progresssnapshot text NOT NULL,
  currentstate text NOT NULL,
  nextaction text NOT NULL,
  isvalid boolean NOT NULL DEFAULT false,
  expiresat bigint,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT session_autosave_pkey PRIMARY KEY (id)
);
CREATE TABLE public.session_exercises (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  sessionid uuid NOT NULL,
  exerciseid text NOT NULL,
  order bigint NOT NULL,
  name character varying NOT NULL,
  targetsets bigint NOT NULL,
  completedsets bigint NOT NULL,
  restseconds bigint,
  restsecondsoverride bigint,
  imageurl text,
  videourl text,
  status text NOT NULL,
  starttime timestamp with time zone,
  endtime timestamp with time zone,
  notes text,
  iscompleted boolean NOT NULL DEFAULT false,
  CONSTRAINT session_exercises_pkey PRIMARY KEY (id),
  CONSTRAINT fk_session_exercises_sessionid FOREIGN KEY (sessionid) REFERENCES public.workout_sessions(id)
);
CREATE TABLE public.session_sets (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  sessionexerciseid uuid NOT NULL,
  setnumber bigint NOT NULL,
  weight numeric,
  weightunit text,
  reps bigint,
  timeseconds bigint,
  rpe numeric,
  iscompleted boolean NOT NULL DEFAULT false,
  iswarmupset boolean NOT NULL DEFAULT false,
  notes text,
  timestamp bigint NOT NULL,
  CONSTRAINT session_sets_pkey PRIMARY KEY (id),
  CONSTRAINT fk_session_sets_sessionexerciseid FOREIGN KEY (sessionexerciseid) REFERENCES public.session_exercises(id)
);
CREATE TABLE public.session_summary (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  range_start bigint NOT NULL,
  range_end bigint NOT NULL,
  summary_content text NOT NULL,
  summary_type text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  original_message_count bigint NOT NULL,
  original_token_count bigint NOT NULL,
  summary_token_count bigint NOT NULL,
  compression_ratio numeric NOT NULL,
  model_used text NOT NULL,
  generation_time_ms bigint,
  quality_score numeric,
  CONSTRAINT session_summary_pkey PRIMARY KEY (id),
  CONSTRAINT fk_session_summary_session_id FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id)
);
CREATE TABLE public.template_exercises (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  templateid uuid NOT NULL,
  exerciseid text NOT NULL,
  order bigint NOT NULL,
  sets bigint NOT NULL,
  repsperset text NOT NULL,
  weightsuggestion text,
  restseconds bigint NOT NULL,
  notes text,
  superset bigint NOT NULL,
  supersetgroupid text,
  CONSTRAINT template_exercises_pkey PRIMARY KEY (id),
  CONSTRAINT fk_template_exercises_templateid FOREIGN KEY (templateid) REFERENCES public.workout_templates(id)
);
CREATE TABLE public.template_versions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  templateid uuid NOT NULL,
  versionnumber bigint NOT NULL,
  contentjson jsonb NOT NULL,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  description text,
  isautosaved boolean NOT NULL DEFAULT false,
  CONSTRAINT template_versions_pkey PRIMARY KEY (id),
  CONSTRAINT fk_template_versions_templateid FOREIGN KEY (templateid) REFERENCES public.workout_templates(id)
);
CREATE TABLE public.tokens (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  accesstoken text NOT NULL,
  refreshtoken text NOT NULL,
  tokentype text NOT NULL,
  expiresin bigint NOT NULL,
  issuedat boolean NOT NULL DEFAULT false,
  userid bigint NOT NULL,
  scope text,
  CONSTRAINT tokens_pkey PRIMARY KEY (id),
  CONSTRAINT fk_tokens_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.user (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT user_pkey PRIMARY KEY (id)
);
CREATE TABLE public.user_profiles (
  userid bigint NOT NULL,
  username character varying,
  displayname character varying,
  email character varying,
  phonenumber text,
  profileimageurl text,
  bio text,
  gender text,
  height numeric,
  heightunit text,
  weight numeric,
  weightunit text,
  fitnesslevel bigint,
  fitnessgoals text NOT NULL,
  workoutdays text NOT NULL,
  allowpartnermatching bigint NOT NULL,
  totalworkoutcount bigint NOT NULL,
  weeklyactiveminutes bigint NOT NULL,
  likesreceived bigint NOT NULL,
  isanonymous boolean NOT NULL DEFAULT false,
  hasvalidsubscription bigint NOT NULL,
  lastupdated bigint NOT NULL,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  profilesummary text,
  vector bytea,
  vectorcreatedat bigint,
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT user_profiles_pkey PRIMARY KEY (userid),
  CONSTRAINT fk_user_profiles_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.user_settings (
  userid bigint NOT NULL,
  thememode text NOT NULL,
  languagecode text NOT NULL,
  measurementsystem text NOT NULL,
  notificationsenabled boolean NOT NULL DEFAULT false,
  soundsenabled boolean NOT NULL DEFAULT false,
  locationsharingenabled boolean NOT NULL DEFAULT false,
  datasharingenabled boolean NOT NULL DEFAULT false,
  allowworkoutsharing bigint NOT NULL,
  autobackupenabled boolean NOT NULL DEFAULT false,
  backupfrequency bigint NOT NULL,
  lastbackuptime bigint NOT NULL,
  allowpartnermatching bigint NOT NULL,
  preferredmatchdistance boolean NOT NULL DEFAULT false,
  matchbyfitnesslevel bigint NOT NULL,
  lastmodified timestamp with time zone NOT NULL,
  CONSTRAINT user_settings_pkey PRIMARY KEY (userid),
  CONSTRAINT fk_user_settings_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.workout_plans (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name character varying NOT NULL,
  description text,
  userid bigint NOT NULL,
  targetgoal text,
  difficultylevel bigint NOT NULL,
  estimatedduration bigint,
  ispublic boolean NOT NULL DEFAULT false,
  istemplate boolean NOT NULL DEFAULT false,
  isfavorite boolean NOT NULL DEFAULT false,
  isaigenerated boolean NOT NULL DEFAULT false,
  tags text NOT NULL,
  totaldays bigint NOT NULL,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  updatedat timestamp with time zone NOT NULL DEFAULT now(),
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT workout_plans_pkey PRIMARY KEY (id),
  CONSTRAINT fk_workout_plans_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.workout_sessions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  userid bigint NOT NULL,
  templateid text NOT NULL,
  templateversion bigint,
  planid text,
  name character varying NOT NULL,
  status text NOT NULL,
  starttime timestamp with time zone NOT NULL,
  endtime timestamp with time zone,
  totalduration bigint,
  totalvolume numeric,
  caloriesburned bigint,
  notes text,
  rating bigint,
  lastautosavetime timestamp with time zone NOT NULL,
  user_type_audit character varying DEFAULT NULL::character varying,
  CONSTRAINT workout_sessions_pkey PRIMARY KEY (id),
  CONSTRAINT fk_workout_sessions_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
CREATE TABLE public.workout_templates (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name character varying NOT NULL,
  description text,
  targetmusclegroups text NOT NULL,
  difficulty bigint NOT NULL,
  estimatedduration bigint,
  userid bigint NOT NULL,
  ispublic boolean NOT NULL DEFAULT false,
  isfavorite boolean NOT NULL DEFAULT false,
  tags text NOT NULL,
  currentversion bigint NOT NULL,
  isdraft boolean NOT NULL DEFAULT false,
  ispublished boolean NOT NULL DEFAULT false,
  lastpublishedat timestamp with time zone,
  versiontag bigint NOT NULL,
  jsondata text,
  createdat timestamp with time zone NOT NULL DEFAULT now(),
  updatedat timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT workout_templates_pkey PRIMARY KEY (id),
  CONSTRAINT fk_workout_templates_userid FOREIGN KEY (userid) REFERENCES public.user(id)
);
