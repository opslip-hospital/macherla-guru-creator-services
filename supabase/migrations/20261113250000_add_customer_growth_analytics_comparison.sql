-- Store optional YouTube Analytics API comparison windows for the Growth Doctor.
alter table public.channel_analytics_snapshots
  add column if not exists analytics_comparison jsonb not null default '{}'::jsonb;
