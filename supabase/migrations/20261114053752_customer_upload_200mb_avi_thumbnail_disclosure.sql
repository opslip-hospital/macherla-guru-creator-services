-- Expand the private customer video intake to 200 MB and support AVI.
-- Add optional customer thumbnails and persist YouTube's synthetic-media disclosure.
alter table public.upload_jobs
  add column if not exists thumbnail_storage_object_path text,
  add column if not exists contains_synthetic_media boolean not null default false;

update storage.buckets
set file_size_limit = 209715200,
    allowed_mime_types = array['video/mp4','video/quicktime','video/webm','video/x-msvideo']
where id = 'customer-video-intake';

drop policy if exists "customer video intake insert own active tenant" on storage.objects;
create policy "customer video intake insert own active tenant"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'customer-video-intake'
  and exists (
    select 1 from public.tenant_memberships m
    join public.tenants t on t.id = m.tenant_id
    where m.tenant_id::text = (storage.foldername(name))[1]
      and m.user_id = (select auth.uid())
      and m.membership_role = 'owner'
      and t.status = 'active'
  )
  and array_length(storage.foldername(name), 1) = 2
  and exists (
    select 1 from public.upload_jobs j
    where j.id::text = (storage.foldername(name))[2]
      and j.tenant_id::text = (storage.foldername(name))[1]
      and j.status = 'draft'
      and (
        j.original_filename = storage.filename(name)
        or storage.filename(name) in ('thumbnail.jpg','thumbnail.png')
      )
  )
);

create or replace function private.set_customer_upload_assets(
  p_job uuid, p_thumbnail_path text, p_contains_synthetic_media boolean
) returns boolean language plpgsql security definer set search_path = ''
as $function$
declare v_tenant uuid; v_status text;
begin
  if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
  select tenant_id,status into v_tenant,v_status from public.upload_jobs where id=p_job for update;
  if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
  if not exists(select 1 from public.tenant_memberships m join public.tenants t on t.id=m.tenant_id
    where m.tenant_id=v_tenant and m.user_id=auth.uid() and m.membership_role='owner' and t.status='active')
    then raise exception 'active workspace owner required' using errcode='42501'; end if;
  if v_status not in ('draft','received') then raise exception 'upload job is locked' using errcode='22023'; end if;
  if p_thumbnail_path is not null then
    if p_thumbnail_path not in (v_tenant::text||'/'||p_job::text||'/thumbnail.jpg',
      v_tenant::text||'/'||p_job::text||'/thumbnail.png') then
      raise exception 'invalid thumbnail path' using errcode='22023'; end if;
    if not exists(select 1 from storage.objects o where o.bucket_id='customer-video-intake'
      and o.name=p_thumbnail_path and o.metadata->>'mimetype' in ('image/jpeg','image/png')
      and coalesce((o.metadata->>'size')::bigint,0) between 1 and 10485760) then
      raise exception 'thumbnail must be JPG or PNG up to 10 MB' using errcode='22023'; end if;
  end if;
  update public.upload_jobs set thumbnail_storage_object_path=p_thumbnail_path,
    contains_synthetic_media=coalesce(p_contains_synthetic_media,false),updated_at=now() where id=p_job;
  return true;
end; $function$;

create or replace function public.set_customer_upload_assets(
  p_job uuid, p_thumbnail_path text, p_contains_synthetic_media boolean
) returns boolean language sql security definer set search_path = ''
as $function$ select private.set_customer_upload_assets(p_job,p_thumbnail_path,p_contains_synthetic_media); $function$;
revoke all on function public.set_customer_upload_assets(uuid,text,boolean) from public,anon;
grant execute on function public.set_customer_upload_assets(uuid,text,boolean) to authenticated;

do $block$
declare v_def text;
begin
  select pg_get_functiondef('private.create_customer_upload_job(uuid,text,text,text,bigint)'::regprocedure) into v_def;
  v_def:=replace(v_def,
    $old$p_mime not in ('video/mp4','video/quicktime','video/webm') or p_size is null or p_size<1 or p_size>104857600$old$,
    $new$p_mime not in ('video/mp4','video/quicktime','video/webm','video/x-msvideo') or p_size is null or p_size<1 or p_size>209715200$new$);
  v_def:=replace(v_def,
    $old$supported formats MP4, MOV, WebM up to 100 MB$old$,
    $new$supported formats MP4, MOV, AVI, WebM up to 200 MB$new$);
  execute v_def;
  select pg_get_functiondef('private.claim_youtube_upload_job(uuid,uuid)'::regprocedure) into v_def;
  v_def:=replace(v_def,
    $old$'storage_object_path',v_job.storage_object_path,'mime_type'$old$,
    $new$'storage_object_path',v_job.storage_object_path,'thumbnail_storage_object_path',v_job.thumbnail_storage_object_path,'contains_synthetic_media',v_job.contains_synthetic_media,'mime_type'$new$);
  execute v_def;
end $block$;
