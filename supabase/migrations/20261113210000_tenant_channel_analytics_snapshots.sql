-- Tenant-scoped read-only YouTube channel analytics snapshots.
create table if not exists public.channel_analytics_snapshots (
 id uuid primary key default gen_random_uuid(),
 tenant_id uuid not null references public.tenants(id) on delete cascade,
 connection_id uuid not null references private.youtube_connections(id) on delete cascade,
 channel_id text not null, channel_title text,
 subscriber_count bigint, view_count bigint, video_count bigint,
 captured_at timestamptz not null default now(), created_at timestamptz not null default now()
);
create index if not exists channel_analytics_tenant_captured_idx on public.channel_analytics_snapshots(tenant_id,captured_at desc);
alter table public.channel_analytics_snapshots enable row level security;
drop policy if exists analytics_select_member_or_admin on public.channel_analytics_snapshots;
create policy analytics_select_member_or_admin on public.channel_analytics_snapshots for select to authenticated using (
 private.is_tenant_member(tenant_id) or private.is_platform_admin()
);
revoke all on table public.channel_analytics_snapshots from anon,authenticated;
grant select on table public.channel_analytics_snapshots to authenticated;
grant insert,select on table public.channel_analytics_snapshots to service_role;
create or replace function private.claim_youtube_analytics(p_tenant uuid,p_admin_user_id uuid)
returns jsonb language plpgsql security definer set search_path=''
as $$
declare v_connection private.youtube_connections%rowtype;
begin
 if p_admin_user_id is null or not exists(select 1 from public.profiles where user_id=p_admin_user_id and role='admin') then raise exception 'platform admin required' using errcode='42501'; end if;
 select * into v_connection from private.youtube_connections where tenant_id=p_tenant and revoked_at is null
  and granted_scopes @> array['https://www.googleapis.com/auth/youtube.readonly']::text[]
  order by connected_at desc limit 1 for update;
 if not found then raise exception 'read-only YouTube connection not found' using errcode='P0002'; end if;
 return jsonb_build_object('tenant_id',p_tenant,'connection_id',v_connection.id,'channel_id',v_connection.channel_id,
  'channel_title',v_connection.channel_title,'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex'));
end; $$;
revoke all on function private.claim_youtube_analytics(uuid,uuid) from public,anon,authenticated;
grant execute on function private.claim_youtube_analytics(uuid,uuid) to service_role;
create or replace function public.claim_youtube_analytics(p_tenant uuid,p_admin_user_id uuid)
returns jsonb language sql security invoker set search_path=''
as $$ select private.claim_youtube_analytics(p_tenant,p_admin_user_id); $$;
revoke all on function public.claim_youtube_analytics(uuid,uuid) from public,anon,authenticated;
grant execute on function public.claim_youtube_analytics(uuid,uuid) to service_role;
