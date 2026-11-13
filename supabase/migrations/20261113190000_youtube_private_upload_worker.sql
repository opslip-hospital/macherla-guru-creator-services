-- Server-only claim operation for the private YouTube upload worker.
alter table public.upload_jobs drop constraint if exists upload_jobs_status_check;
alter table public.upload_jobs add constraint upload_jobs_status_check
 check (status in ('draft','received','processing','uploaded_private','awaiting_approval','approved','scheduled','published','failed','cancelled'));
create or replace function private.claim_youtube_upload_job(p_job_id uuid,p_admin_user_id uuid)
returns jsonb language plpgsql security definer set search_path=''
as $$
declare v_job public.upload_jobs%rowtype; v_connection private.youtube_connections%rowtype; v_metadata public.content_metadata%rowtype;
begin
 if p_admin_user_id is null or not exists(select 1 from public.profiles where user_id=p_admin_user_id and role='admin') then
  raise exception 'platform admin required' using errcode='42501'; end if;
 select * into v_job from public.upload_jobs where id=p_job_id for update;
 if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
 if v_job.status<>'received' or v_job.storage_object_path is null then
  raise exception 'video file is not ready for YouTube upload' using errcode='22023'; end if;
 select * into v_connection from private.youtube_connections
  where tenant_id=v_job.tenant_id and revoked_at is null
   and granted_scopes @> array['https://www.googleapis.com/auth/youtube.upload']::text[]
  order by connected_at desc limit 1 for update;
 if not found then raise exception 'connected YouTube upload permission not found' using errcode='P0002'; end if;
 select * into v_metadata from public.content_metadata where upload_job_id=p_job_id order by created_at desc limit 1;
 update public.upload_jobs set status='processing',connection_id=v_connection.id,updated_at=now() where id=p_job_id;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
 values(v_job.tenant_id,p_admin_user_id,'youtube_private_upload_started',jsonb_build_object('upload_job_id',p_job_id,'channel_id',v_connection.channel_id));
 return jsonb_build_object(
  'job_id',v_job.id,'tenant_id',v_job.tenant_id,'storage_object_path',v_job.storage_object_path,
  'mime_type',v_job.mime_type,'file_size_bytes',v_job.file_size_bytes,
  'video_title',coalesce(v_metadata.title,v_job.video_title),'description',coalesce(v_metadata.description,''),
  'tags',coalesce(to_jsonb(v_metadata.tags),'[]'::jsonb),'hashtags',coalesce(to_jsonb(v_metadata.hashtags),'[]'::jsonb),
  'channel_id',v_connection.channel_id,'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex'));
end; $$;
revoke all on function private.claim_youtube_upload_job(uuid,uuid) from public,anon,authenticated;
grant execute on function private.claim_youtube_upload_job(uuid,uuid) to service_role;
create or replace function public.claim_youtube_upload_job(p_job_id uuid,p_admin_user_id uuid)
returns jsonb language sql security invoker set search_path=''
as $$ select private.claim_youtube_upload_job(p_job_id,p_admin_user_id); $$;
revoke all on function public.claim_youtube_upload_job(uuid,uuid) from public,anon,authenticated;
grant execute on function public.claim_youtube_upload_job(uuid,uuid) to service_role;
