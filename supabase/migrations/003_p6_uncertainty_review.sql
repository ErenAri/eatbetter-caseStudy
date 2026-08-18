alter table public.meal_items
  add column observation_certainty text check (
    observation_certainty is null or observation_certainty in ('HIGH', 'MEDIUM', 'LOW')
  ),
  add column portion_resolution_source text check (
    portion_resolution_source is null or portion_resolution_source in (
      'AUTO_ESTIMATE', 'USER', 'USER_HOUSEHOLD_UNIT'
    )
  );

alter table public.clarifications
  add column blocking boolean not null default true,
  add column stable_key text,
  add column resolution_satisfied boolean not null default false;

create unique index clarifications_meal_stable_key_unique
  on public.clarifications (meal_id, stable_key)
  where stable_key is not null;
