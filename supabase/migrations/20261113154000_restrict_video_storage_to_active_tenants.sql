
drop policy if exists "customer video intake insert own tenant" on storage.objects;
create policy "customer video intake insert own active tenant"
on storage.objects for insert to authenticated
with check (
 bucket_id='customer-video-intake'
 and exists (
  select 1 from public.tenant_memberships m
  join public.tenants t on t.id=m.tenant_id
  where m.tenant_id::text=(storage.foldername(objects.name))[1]
    and m.user_id=auth.uid()
    and m.membership_role='owner'
    and t.status='active'
 )
 and (storage.foldername(name))[2] is not null
);
