-- YouTube OAuth state, encrypted refresh-token storage, and safe status RPCs.
create table if not exists private.youtube_oauth_states (
  state_hash text primary key check (length(state_hash) = 64),
  user_id uuid not null references auth.users(id) on delete cascade,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  used_at timestamptz
);
alter table private.youtube_oauth_states enable row level security;
revoke all on table private.youtube_oauth_states from public, anon, authenticated;
grant usage on schema private to service_role;
grant select, insert, update, delete on private.youtube_oauth_states to service_role;
grant select, insert, update on private.youtube_connections to service_role;
create index if not exists youtube_oauth_states_expiry_idx on private.youtube_oauth_states(expires_at);

create or replace function public.create_youtube_oauth_state(
  p_user_id uuid, p_tenant_id uuid, p_state_hash text, p_expires_at timestamptz
) returns boolean language plpgsql security invoker set search_path = ''
as $$
begin
  if p_user_id is null or p_tenant_id is null or p_state_hash is null
     or length(p_state_hash) <> 64 or p_expires_at <= now()
     or p_expires_at > now() + interval '15 minutes' then
    raise exception 'invalid OAuth state request' using errcode='22023';
  end if;
  if not exists (
    select 1 from public.tenant_memberships m
    join public.tenants t on t.id=m.tenant_id
    where m.user_id=p_user_id and m.tenant_id=p_tenant_id
      and m.membership_role='owner' and t.status='active'
  ) then raise exception 'active workspace owner required' using errcode='42501'; end if;
  insert into private.youtube_oauth_states(state_hash,user_id,tenant_id,expires_at)
  values(p_state_hash,p_user_id,p_tenant_id,p_expires_at);
  return true;
end;
$$;
revoke all on function public.create_youtube_oauth_state(uuid,uuid,text,timestamptz) from public, anon, authenticated;
grant execute on function public.create_youtube_oauth_state(uuid,uuid,text,timestamptz) to service_role;

create or replace function public.complete_youtube_oauth(
  p_state_hash text, p_channel_id text, p_channel_title text,
  p_encrypted_refresh_token bytea, p_granted_scopes text[]
) returns uuid language plpgsql security invoker set search_path = ''
as $$
declare v_user_id uuid; v_tenant_id uuid; v_connection_id uuid;
begin
  if p_state_hash is null or length(p_state_hash) <> 64
     or p_channel_id is null or length(p_channel_id) < 3
     or p_encrypted_refresh_token is null
     or octet_length(p_encrypted_refresh_token) < 32 then
    raise exception 'invalid OAuth completion payload' using errcode='22023';
  end if;
  update private.youtube_oauth_states s set used_at=now()
   where s.state_hash=p_state_hash and s.used_at is null and s.expires_at > now()
   returning s.user_id,s.tenant_id into v_user_id,v_tenant_id;
  if not found then raise exception 'OAuth state expired or already used' using errcode='P0002'; end if;
  if not exists (
    select 1 from public.tenant_memberships m join public.tenants t on t.id=m.tenant_id
    where m.user_id=v_user_id and m.tenant_id=v_tenant_id
      and m.membership_role='owner' and t.status='active'
  ) then raise exception 'workspace owner access no longer active' using errcode='42501'; end if;
  insert into private.youtube_connections(
    tenant_id,channel_id,channel_title,encrypted_refresh_token,granted_scopes,connected_at,revoked_at
  ) values (
    v_tenant_id,p_channel_id,p_channel_title,p_encrypted_refresh_token,
    coalesce(p_granted_scopes,'{}'::text[]),now(),null
  )
  on conflict (tenant_id,channel_id) do update
    set channel_title=excluded.channel_title,
        encrypted_refresh_token=excluded.encrypted_refresh_token,
        granted_scopes=excluded.granted_scopes, connected_at=now(), revoked_at=null
  returning id into v_connection_id;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
  values(v_tenant_id,v_user_id,'youtube_channel_connected',
    jsonb_build_object('channel_id',p_channel_id,'channel_title',p_channel_title));
  return v_connection_id;
end;
$$;
revoke all on function public.complete_youtube_oauth(text,text,text,bytea,text[]) from public, anon, authenticated;
grant execute on function public.complete_youtube_oauth(text,text,text,bytea,text[]) to service_role;

create or replace function private.list_tenant_youtube_connections(target_tenant uuid)
returns table(channel_id text, channel_title text, connected_at timestamptz, granted_scopes text[])
language plpgsql stable security definer set search_path = ''
as $$
begin
  if auth.uid() is null or not (private.is_platform_admin() or private.is_tenant_member(target_tenant)) then
    raise exception 'not authorized' using errcode='42501';
  end if;
  return query select c.channel_id,c.channel_title,c.connected_at,c.granted_scopes
    from private.youtube_connections c
    where c.tenant_id=target_tenant and c.revoked_at is null order by c.connected_at desc;
end;
$$;
revoke all on function private.list_tenant_youtube_connections(uuid) from public, anon;
grant execute on function private.list_tenant_youtube_connections(uuid) to authenticated;
create or replace function public.list_tenant_youtube_connections(target_tenant uuid)
returns table(channel_id text, channel_title text, connected_at timestamptz, granted_scopes text[])
language sql stable security invoker set search_path = ''
as $$ select * from private.list_tenant_youtube_connections(target_tenant); $$;
revoke all on function public.list_tenant_youtube_connections(uuid) from public, anon;
grant execute on function public.list_tenant_youtube_connections(uuid) to authenticated;
