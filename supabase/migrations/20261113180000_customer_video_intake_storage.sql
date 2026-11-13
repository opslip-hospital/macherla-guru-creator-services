-- Secure customer video intake into a private tenant-scoped Storage bucket.
insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
values ('customer-video-intake','customer-video-intake',false,104857600,
  array['video/mp4','video/quicktime','video/webm'])
on conflict (id) do update set public=false,file_size_limit=104857600,allowed_mime_types=excluded.allowed_mime_types;
alter table public.upload_jobs
  add column if not exists storage_object_path text,
  add column if not exists original_filename text,
  add column if not exists file_size_bytes bigint,
  add column if not exists mime_type text;
alter table public.upload_jobs drop constraint if exists upload_jobs_status_check;
alter table public.upload_jobs add constraint upload_jobs_status_check
  check (status in ('draft','received','uploaded_private','awaiting_approval','approved','scheduled','published','failed','cancelled'));
create or replace function private.create_customer_upload_job(p_tenant uuid,p_title text,p_filename text,p_mime text,p_size bigint)
returns uuid language plpgsql security definer set search_path=''
as $$
declare v_job uuid;
begin
 if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=p_tenant and user_id=auth.uid() and membership_role='owner') then
  raise exception 'workspace owner required' using errcode='42501'; end if;
 if length(btrim(coalesce(p_title,'')))<1 or length(p_title)>100
  or length(btrim(coalesce(p_filename,'')))<1 or length(p_filename)>255
  or p_mime not in ('video/mp4','video/quicktime','video/webm')
  or p_size is null or p_size<1 or p_size>104857600 then
  raise exception 'invalid upload details; supported formats MP4, MOV, WebM up to 100 MB' using errcode='22023'; end if;
 insert into public.upload_jobs(tenant_id,video_title,status,original_filename,mime_type,file_size_bytes)
 values(p_tenant,btrim(p_title),'draft',p_filename,p_mime,p_size) returning id into v_job;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
 values(p_tenant,auth.uid(),'customer_video_intake_created',jsonb_build_object('upload_job_id',v_job,'filename',p_filename,'mime_type',p_mime,'size_bytes',p_size));
 return v_job;
end; $$;
revoke all on function private.create_customer_upload_job(uuid,text,text,text,bigint) from public,anon;
grant execute on function private.create_customer_upload_job(uuid,text,text,text,bigint) to authenticated;
create or replace function private.finalize_customer_video_upload(p_job uuid,p_object_path text)
returns boolean language plpgsql security definer set search_path=''
as $$
declare v_tenant uuid; v_status text; v_filename text;
begin
 if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
 select tenant_id,status,original_filename into v_tenant,v_status,v_filename from public.upload_jobs where id=p_job for update;
 if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
 if not exists(select 1 from public.tenant_memberships where tenant_id=v_tenant and user_id=auth.uid() and membership_role='owner') then
  raise exception 'workspace owner required' using errcode='42501'; end if;
 if v_status<>'draft' or p_object_path<>v_tenant::text||'/'||p_job::text||'/'||v_filename then
  raise exception 'invalid upload state or object path' using errcode='22023'; end if;
 update public.upload_jobs set storage_object_path=p_object_path,status='received',updated_at=now() where id=p_job;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
 values(v_tenant,auth.uid(),'customer_video_file_received',jsonb_build_object('upload_job_id',p_job,'object_path',p_object_path));
 return true;
end; $$;
revoke all on function private.finalize_customer_video_upload(uuid,text) from public,anon;
grant execute on function private.finalize_customer_video_upload(uuid,text) to authenticated;
create or replace function public.create_customer_upload_job(p_tenant uuid,p_title text,p_filename text,p_mime text,p_size bigint)
returns uuid language sql security invoker set search_path=''
as $$ select private.create_customer_upload_job(p_tenant,p_title,p_filename,p_mime,p_size); $$;
revoke all on function public.create_customer_upload_job(uuid,text,text,text,bigint) from public,anon;
grant execute on function public.create_customer_upload_job(uuid,text,text,text,bigint) to authenticated;
create or replace function public.finalize_customer_video_upload(p_job uuid,p_object_path text)
returns boolean language sql security invoker set search_path=''
as $$ select private.finalize_customer_video_upload(p_job,p_object_path); $$;
revoke all on function public.finalize_customer_video_upload(uuid,text) from public,anon;
grant execute on function public.finalize_customer_video_upload(uuid,text) to authenticated;
drop policy if exists "customer video intake insert own tenant" on storage.objects;
create policy "customer video intake insert own tenant" on storage.objects for insert to authenticated with check (
 bucket_id='customer-video-intake'
 and exists(select 1 from public.tenant_memberships m where m.tenant_id::text=(storage.foldername(name))[1] and m.user_id=auth.uid() and m.membership_role='owner')
 and (storage.foldername(name))[2] is not null
);
drop policy if exists "customer video intake read own tenant or admin" on storage.objects;
create policy "customer video intake read own tenant or admin" on storage.objects for select to authenticated using (
 bucket_id='customer-video-intake' and (private.is_platform_admin() or exists(
 select 1 from public.tenant_memberships m where m.tenant_id::text=(storage.foldername(name))[1] and m.user_id=auth.uid() and m.membership_role='owner'))
);
