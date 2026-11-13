drop policy if exists "customer video intake insert own active tenant" on storage.objects;
create policy "customer video intake insert own active tenant"
on storage.objects
for insert to authenticated
with check (
  bucket_id = 'customer-video-intake'
  and exists (
    select 1
    from public.tenant_memberships m
    join public.tenants t on t.id = m.tenant_id
    where m.tenant_id::text = (storage.foldername(objects.name))[1]
      and m.user_id = (select auth.uid())
      and m.membership_role = 'owner'
      and t.status = 'active'
  )
  and array_length(storage.foldername(objects.name), 1) = 2
  and exists (
    select 1
    from public.upload_jobs j
    where j.id::text = (storage.foldername(objects.name))[2]
      and j.tenant_id::text = (storage.foldername(objects.name))[1]
      and j.original_filename = storage.filename(objects.name)
      and j.status = 'draft'
  )
);
