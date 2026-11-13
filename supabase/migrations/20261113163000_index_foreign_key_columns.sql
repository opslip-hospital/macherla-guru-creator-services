create index if not exists youtube_oauth_states_tenant_id_idx on private.youtube_oauth_states (tenant_id);
create index if not exists youtube_oauth_states_user_id_idx on private.youtube_oauth_states (user_id);
create index if not exists channel_analytics_snapshots_connection_id_idx on public.channel_analytics_snapshots (connection_id);
create index if not exists customer_requests_reviewed_by_idx on public.customer_requests (reviewed_by);
