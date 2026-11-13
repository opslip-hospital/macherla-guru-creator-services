
create or replace function private.create_customer_upload_job(p_tenant uuid,p_title text,p_filename text,p_mime text,p_size bigint)
returns uuid language plpgsql security definer set search_path = '' as $$
declare v_job uuid;
begin
 if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
 if not exists(select 1 from public.tenant_memberships m join public.tenants t on t.id=m.tenant_id where m.tenant_id=p_tenant and m.user_id=auth.uid() and m.membership_role='owner' and t.status='active') then
  raise exception 'active workspace owner required' using errcode='42501'; end if;
 if length(btrim(coalesce(p_title,'')))<1 or length(p_title)>100 or length(btrim(coalesce(p_filename,'')))<1 or length(p_filename)>255
 or p_mime not in ('video/mp4','video/quicktime','video/webm') or p_size is null or p_size<1 or p_size>104857600 then
  raise exception 'invalid upload details; supported formats MP4, MOV, WebM up to 100 MB' using errcode='22023'; end if;
 insert into public.upload_jobs(tenant_id,video_title,status,original_filename,mime_type,file_size_bytes)
 values(p_tenant,btrim(p_title),'draft',p_filename,p_mime,p_size) returning id into v_job;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
 values(p_tenant,auth.uid(),'customer_video_intake_created',jsonb_build_object('upload_job_id',v_job,'filename',p_filename,'mime_type',p_mime,'size_bytes',p_size));
 return v_job;
end; $$;

create or replace function private.finalize_customer_video_upload(p_job uuid,p_object_path text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare v_tenant uuid; v_status text;
begin
 if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
 select tenant_id,status into v_tenant,v_status from public.upload_jobs where id=p_job for update;
 if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
 if not exists(select 1 from public.tenant_memberships m join public.tenants t on t.id=m.tenant_id where m.tenant_id=v_tenant and m.user_id=auth.uid() and m.membership_role='owner' and t.status='active') then
  raise exception 'active workspace owner required' using errcode='42501'; end if;
 if v_status<>'draft' or p_object_path<>v_tenant::text||'/'||p_job::text||'/'||(select original_filename from public.upload_jobs where id=p_job) then
  raise exception 'invalid upload state or object path' using errcode='22023'; end if;
 update public.upload_jobs set storage_object_path=p_object_path,status='received',updated_at=now() where id=p_job;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details) values(v_tenant,auth.uid(),'customer_video_file_received',jsonb_build_object('upload_job_id',p_job,'object_path',p_object_path));
 return true;
end; $$;

create or replace function private.claim_youtube_upload_job(p_job_id uuid,p_admin_user_id uuid)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare v_job public.upload_jobs%rowtype; v_connection private.youtube_connections%rowtype; v_metadata public.content_metadata%rowtype;
begin
 if auth.uid() is null or p_admin_user_id is distinct from auth.uid() then raise exception 'authenticated customer required' using errcode='42501'; end if;
 select * into v_job from public.upload_jobs where id=p_job_id for update;
 if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
 if not exists(select 1 from public.tenant_memberships m join public.tenants t on t.id=m.tenant_id where m.tenant_id=v_job.tenant_id and m.user_id=auth.uid() and m.membership_role='owner' and t.status='active') then
  raise exception 'active workspace owner required' using errcode='42501'; end if;
 if v_job.status<>'received' or v_job.storage_object_path is null then raise exception 'video file is not ready for YouTube upload' using errcode='22023'; end if;
 select * into v_connection from private.youtube_connections where tenant_id=v_job.tenant_id and revoked_at is null
  and granted_scopes @> array['https://www.googleapis.com/auth/youtube.upload']::text[] order by connected_at desc limit 1 for update;
 if not found then raise exception 'connected YouTube upload permission not found' using errcode='P0002'; end if;
 select * into v_metadata from public.content_metadata where upload_job_id=p_job_id order by created_at desc limit 1;
 update public.upload_jobs set status='processing',connection_id=v_connection.id,updated_at=now() where id=p_job_id;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details) values(v_job.tenant_id,auth.uid(),'youtube_private_upload_started',jsonb_build_object('upload_job_id',p_job_id,'channel_id',v_connection.channel_id,'actor_role','customer_owner'));
 return jsonb_build_object('job_id',v_job.id,'tenant_id',v_job.tenant_id,'storage_object_path',v_job.storage_object_path,'mime_type',v_job.mime_type,'file_size_bytes',v_job.file_size_bytes,'video_title',coalesce(v_metadata.title,v_job.video_title),'description',coalesce(v_metadata.description,''),'tags',coalesce(to_jsonb(v_metadata.tags),'[]'::jsonb),'hashtags',coalesce(to_jsonb(v_metadata.hashtags),'[]'::jsonb),'metadata_details',coalesce(v_metadata.metadata_details,'{}'::jsonb),'channel_id',v_connection.channel_id,'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex'));
end; $$;

create or replace function private.claim_youtube_publish_job(p_job_id uuid,p_admin_user_id uuid,p_mode text,p_publish_at timestamp with time zone default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare v_job public.upload_jobs%rowtype; v_connection private.youtube_connections%rowtype;
begin
 if auth.uid() is null or p_admin_user_id is distinct from auth.uid() then raise exception 'authenticated customer required' using errcode='42501'; end if;
 if p_mode not in ('now','schedule') then raise exception 'invalid publish mode' using errcode='22023'; end if;
 if p_mode='schedule' and (p_publish_at is null or p_publish_at < now()+interval '15 minutes') then raise exception 'scheduled publish time must be at least 15 minutes in the future' using errcode='22023'; end if;
 if p_mode='now' and p_publish_at is not null then raise exception 'publish time not allowed for immediate publish' using errcode='22023'; end if;
 select * into v_job from public.upload_jobs where id=p_job_id for update;
 if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
 if not exists(select 1 from public.tenant_memberships m join public.tenants t on t.id=m.tenant_id where m.tenant_id=v_job.tenant_id and m.user_id=auth.uid() and m.membership_role='owner' and t.status='active') then
  raise exception 'active workspace owner required' using errcode='42501'; end if;
 if v_job.status not in ('uploaded_private','approved') or v_job.youtube_video_id is null then raise exception 'private YouTube upload required before publishing' using errcode='22023'; end if;
 select * into v_connection from private.youtube_connections where id=v_job.connection_id and tenant_id=v_job.tenant_id and revoked_at is null
  and granted_scopes @> array['https://www.googleapis.com/auth/youtube.force-ssl']::text[] for update;
 if not found then raise exception 'publishing permission not connected; reconnect YouTube' using errcode='42501'; end if;
 update public.upload_jobs set status='publishing',scheduled_for=p_publish_at,updated_at=now() where id=p_job_id;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details) values(v_job.tenant_id,auth.uid(),'youtube_publish_execution_started',jsonb_build_object('upload_job_id',p_job_id,'mode',p_mode,'publish_at',p_publish_at,'explicit_customer_action',true));
 return jsonb_build_object('job_id',v_job.id,'tenant_id',v_job.tenant_id,'youtube_video_id',v_job.youtube_video_id,'channel_id',v_connection.channel_id,'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex'),'mode',p_mode,'publish_at',p_publish_at);
end; $$;
