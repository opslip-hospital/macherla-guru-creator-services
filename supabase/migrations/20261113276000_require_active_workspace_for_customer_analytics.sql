
create or replace function private.claim_youtube_analytics(p_tenant uuid,p_admin_user_id uuid)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
 v_connection private.youtube_connections%rowtype;
 v_is_admin boolean;
begin
 if p_admin_user_id is null then raise exception 'authenticated user required' using errcode='42501'; end if;
 select exists(select 1 from public.profiles where user_id=p_admin_user_id and role='admin') into v_is_admin;
 if not v_is_admin and not exists(
   select 1 from public.tenant_memberships m
   join public.tenants t on t.id=m.tenant_id
   where m.tenant_id=p_tenant and m.user_id=p_admin_user_id
     and m.membership_role='owner' and t.status='active'
 ) then
  raise exception 'active workspace owner or platform admin required' using errcode='42501';
 end if;
 select * into v_connection from private.youtube_connections
  where tenant_id=p_tenant and revoked_at is null
   and granted_scopes @> array['https://www.googleapis.com/auth/youtube.readonly']::text[]
  order by connected_at desc limit 1 for update;
 if not found then raise exception 'read-only YouTube connection not found' using errcode='P0002'; end if;
 return jsonb_build_object('tenant_id',p_tenant,'connection_id',v_connection.id,'channel_id',v_connection.channel_id,
  'channel_title',v_connection.channel_title,'granted_scopes',to_jsonb(v_connection.granted_scopes),
  'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex'));
end; $$;
