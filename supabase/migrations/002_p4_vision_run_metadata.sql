alter table public.ai_runs
  add column image_detail text,
  add column reasoning_effort text,
  add column retry_count integer not null default 0 check (retry_count >= 0);
