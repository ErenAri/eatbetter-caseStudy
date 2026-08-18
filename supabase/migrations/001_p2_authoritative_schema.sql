create extension if not exists pgcrypto;

create type public.meal_status as enum (
  'UPLOADED',
  'ANALYZING',
  'NEEDS_REVIEW',
  'CONFIRMED',
  'FAILED_RETRYABLE',
  'FAILED_PERMANENT'
);

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id) values (new.id)
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger auth_user_created_profile
after insert on auth.users
for each row execute function public.handle_new_auth_user();

insert into public.profiles (id)
select id from auth.users
on conflict (id) do nothing;

create table public.meals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  meal_request_id uuid not null,
  status public.meal_status not null default 'UPLOADED',
  image_path text,
  user_context text check (user_context is null or char_length(user_context) <= 1000),
  logged_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  confirmed_at timestamptz,
  failure_code text,
  failure_message text,
  constraint meals_user_request_unique unique (user_id, meal_request_id)
);

create index meals_user_logged_at_idx on public.meals (user_id, logged_at desc);
create index meals_user_status_idx on public.meals (user_id, status);

create table public.meal_items (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references public.meals(id) on delete cascade,
  position integer not null check (position >= 0),
  observed_name text not null check (char_length(observed_name) > 0),
  normalized_name text,
  preparation_method text,
  canonical_food_id text,
  canonical_food_name text,
  canonical_source text,
  canonical_candidate_rank integer check (canonical_candidate_rank is null or canonical_candidate_rank >= 1),
  portion_min_g numeric(10,3) check (portion_min_g is null or portion_min_g >= 0),
  portion_max_g numeric(10,3) check (portion_max_g is null or portion_max_g >= 0),
  confirmed_portion_g numeric(10,3) check (confirmed_portion_g is null or confirmed_portion_g >= 0),
  canonical_confidence numeric(5,4) check (
    canonical_confidence is null or canonical_confidence between 0 and 1
  ),
  requires_clarification boolean not null default false,
  clarification_resolved boolean not null default false,
  is_removed boolean not null default false,
  is_user_added boolean not null default false,
  final_calories_kcal numeric(12,4) check (final_calories_kcal is null or final_calories_kcal >= 0),
  final_protein_g numeric(12,4) check (final_protein_g is null or final_protein_g >= 0),
  final_carbs_g numeric(12,4) check (final_carbs_g is null or final_carbs_g >= 0),
  final_fat_g numeric(12,4) check (final_fat_g is null or final_fat_g >= 0),
  nutrition_source text,
  nutrition_source_food_id text,
  calories_per_100g numeric(12,4) check (calories_per_100g is null or calories_per_100g >= 0),
  protein_per_100g numeric(12,4) check (protein_per_100g is null or protein_per_100g >= 0),
  carbs_per_100g numeric(12,4) check (carbs_per_100g is null or carbs_per_100g >= 0),
  fat_per_100g numeric(12,4) check (fat_per_100g is null or fat_per_100g >= 0),
  nutrition_retrieved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meal_items_position_unique unique (meal_id, position),
  constraint meal_items_portion_range check (
    portion_min_g is null or portion_max_g is null or portion_max_g >= portion_min_g
  )
);

create index meal_items_meal_idx on public.meal_items (meal_id);

create table public.food_candidates (
  id uuid primary key default gen_random_uuid(),
  meal_item_id uuid not null references public.meal_items(id) on delete cascade,
  rank integer not null check (rank >= 1),
  source text not null,
  source_food_id text not null,
  name text not null,
  data jsonb,
  created_at timestamptz not null default now(),
  constraint food_candidates_rank_unique unique (meal_item_id, rank)
);

create index food_candidates_item_idx on public.food_candidates (meal_item_id);

create table public.ai_runs (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references public.meals(id) on delete cascade,
  stage text not null check (stage in ('MEAL_RECOGNITION', 'CANONICALIZATION', 'PORTION_REASONING')),
  provider text not null,
  model text not null,
  prompt_version text not null,
  status text not null check (status in ('STARTED', 'SUCCEEDED', 'FAILED')),
  started_at timestamptz not null,
  completed_at timestamptz,
  latency_ms integer check (latency_ms is null or latency_ms >= 0),
  input_tokens integer check (input_tokens is null or input_tokens >= 0),
  output_tokens integer check (output_tokens is null or output_tokens >= 0),
  estimated_cost_usd numeric(12,6) check (estimated_cost_usd is null or estimated_cost_usd >= 0),
  request_id uuid,
  error_code text,
  structured_output jsonb,
  created_at timestamptz not null default now()
);

create index ai_runs_meal_stage_idx on public.ai_runs (meal_id, stage, created_at desc);

create table public.corrections (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references public.meals(id) on delete cascade,
  meal_item_id uuid references public.meal_items(id) on delete cascade,
  field_name text not null,
  predicted_value jsonb,
  corrected_value jsonb not null,
  correction_source text not null default 'USER',
  created_at timestamptz not null default now()
);

create index corrections_meal_idx on public.corrections (meal_id, created_at);

create table public.clarifications (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references public.meals(id) on delete cascade,
  meal_item_id uuid references public.meal_items(id) on delete cascade,
  type text not null,
  question text not null,
  options jsonb check (options is null or jsonb_typeof(options) = 'array'),
  reason_codes jsonb not null check (jsonb_typeof(reason_codes) = 'array'),
  status text not null check (status in ('PENDING', 'ANSWERED', 'DISMISSED')),
  answer jsonb,
  created_at timestamptz not null default now(),
  answered_at timestamptz
);

create index clarifications_meal_status_idx on public.clarifications (meal_id, status);

create function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function public.set_updated_at();
create trigger meals_set_updated_at before update on public.meals
for each row execute function public.set_updated_at();
create trigger meal_items_set_updated_at before update on public.meal_items
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.meals enable row level security;
alter table public.meal_items enable row level security;
alter table public.food_candidates enable row level security;
alter table public.ai_runs enable row level security;
alter table public.corrections enable row level security;
alter table public.clarifications enable row level security;

create policy profiles_owner_all on public.profiles
for all using (id = auth.uid()) with check (id = auth.uid());
create policy meals_owner_all on public.meals
for all using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy meal_items_owner_all on public.meal_items
for all using (
  exists (select 1 from public.meals where meals.id = meal_items.meal_id and meals.user_id = auth.uid())
) with check (
  exists (select 1 from public.meals where meals.id = meal_items.meal_id and meals.user_id = auth.uid())
);

create policy food_candidates_owner_all on public.food_candidates
for all using (
  exists (
    select 1 from public.meal_items
    join public.meals on meals.id = meal_items.meal_id
    where meal_items.id = food_candidates.meal_item_id and meals.user_id = auth.uid()
  )
) with check (
  exists (
    select 1 from public.meal_items
    join public.meals on meals.id = meal_items.meal_id
    where meal_items.id = food_candidates.meal_item_id and meals.user_id = auth.uid()
  )
);

create policy ai_runs_owner_all on public.ai_runs
for all using (
  exists (select 1 from public.meals where meals.id = ai_runs.meal_id and meals.user_id = auth.uid())
) with check (
  exists (select 1 from public.meals where meals.id = ai_runs.meal_id and meals.user_id = auth.uid())
);

create policy corrections_owner_all on public.corrections
for all using (
  exists (select 1 from public.meals where meals.id = corrections.meal_id and meals.user_id = auth.uid())
) with check (
  exists (select 1 from public.meals where meals.id = corrections.meal_id and meals.user_id = auth.uid())
);

create policy clarifications_owner_all on public.clarifications
for all using (
  exists (select 1 from public.meals where meals.id = clarifications.meal_id and meals.user_id = auth.uid())
) with check (
  exists (select 1 from public.meals where meals.id = clarifications.meal_id and meals.user_id = auth.uid())
);
