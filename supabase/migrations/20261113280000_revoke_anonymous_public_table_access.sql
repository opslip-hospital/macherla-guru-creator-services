-- Remove inherited API table privileges from anonymous callers.
-- RLS remains the row-level boundary for authenticated customers.
revoke all privileges on all tables in schema public from anon;
revoke all privileges on all sequences in schema public from anon;
