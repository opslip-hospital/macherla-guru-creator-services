-- Reconcile analytics/SEO fields required by the current dashboard.
-- IF NOT EXISTS keeps this safe on already-provisioned projects while ensuring
-- a clean migration replay produces the same schema as the live database.
alter table public.channel_analytics_snapshots
  add column if not exists recent_uploads jsonb not null default '[]'::jsonb,
  add column if not exists channel_description text,
  add column if not exists analytics_comparison jsonb not null default '{}'::jsonb;

alter table public.content_metadata
  add column if not exists metadata_details jsonb not null default '{}'::jsonb;
