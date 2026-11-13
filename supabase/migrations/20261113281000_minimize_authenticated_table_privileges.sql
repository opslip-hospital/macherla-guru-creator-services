-- Restrict authenticated table privileges to the minimum used by the app.
-- Row-level policies continue to scope all SELECT and service-ticket INSERT operations.
revoke all privileges on all tables in schema public from authenticated;
revoke all privileges on all sequences in schema public from authenticated;
grant select on all tables in schema public to authenticated;
grant insert on table public.service_tickets to authenticated;
