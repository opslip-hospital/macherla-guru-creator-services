-- Keep the upload state machine compatible with ambiguous YouTube network outcomes.
-- This must run after all workflow migrations that rewrite the status constraint.
alter table public.upload_jobs drop constraint if exists upload_jobs_status_check;
alter table public.upload_jobs add constraint upload_jobs_status_check
check (status = any (array[
  'draft','received','processing','uploaded_private','awaiting_approval','approved',
  'publishing','scheduled','published','failed','cancelled','upload_unknown'
]::text[]));
