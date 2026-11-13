-- Store the additional AI SEO fields used by the customer Manager-style editor.
alter table public.content_metadata
  add column if not exists metadata_details jsonb not null default '{}'::jsonb;
