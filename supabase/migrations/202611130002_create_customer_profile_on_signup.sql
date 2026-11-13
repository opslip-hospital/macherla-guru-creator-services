create or replace function public.handle_new_creator_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (user_id, display_name, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    'customer'
  )
  on conflict (user_id) do nothing;
  return new;
end;
$$;
drop trigger if exists on_auth_user_created_creator_services on auth.users;
create trigger on_auth_user_created_creator_services
after insert on auth.users
for each row execute function public.handle_new_creator_user();
revoke all on function public.handle_new_creator_user() from public, anon, authenticated;
