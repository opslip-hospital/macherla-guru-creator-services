-- Return granted OAuth scopes so the analytics worker can request deeper reports only when consented.
create or replace function private.claim_youtube_analytics(p_tenant uuid,p_admin_user_id uuid)
returns jsonb language plpgsql security definer set search_path=''
as $$
declare v_connection private.youtube_connections%rowtype;
begin
 if p_admin_user_id is null or not (
   exists(select 1 from public.profiles where user_id=p_admin_user_id and role='admin')
   or exists(select 1 from public.tenant_memberships where tenant_id=p_tenant and user_id=p_admin_user_id and membership_role='owner')
 ) then
  raise exception 'workspace owner or platform admin required' using errcode='42501';
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
