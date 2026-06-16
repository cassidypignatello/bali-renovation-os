-- Migration: 013_enable_rls_security.sql
-- Purpose: Resolve Supabase security advisor findings (the RLS-disabled email alert).
-- Date: 2026-06-17
--
-- Architecture note: the FastAPI backend is the ONLY database client and it
-- connects with the Supabase service-role key, which bypasses RLS entirely.
-- The frontend never touches Supabase directly (no client, no anon key) — it
-- calls the backend API. Therefore enabling RLS with NO public policies is the
-- correct secure-by-default posture: the backend keeps full access, and any
-- direct anon/publishable-key access through PostgREST is denied.

-- ============================================
-- 1. Enable RLS on the 5 tables flagged ERROR (RLS disabled in public)
--    No policies are added → backend-only via the service-role key.
-- ============================================

ALTER TABLE public.materials      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scrape_jobs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workers        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.worker_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.worker_unlocks ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 2. Drop the permissive WITH CHECK (true) INSERT/UPDATE policies flagged WARN.
--    These granted unrestricted writes to the anon/public role; the app never
--    uses the anon key for writes (service-role backend), so dropping them
--    closes a theoretical hole with zero functional impact. RLS stays enabled
--    on these tables; their scoped session-based SELECT policies are untouched.
-- ============================================

DROP POLICY IF EXISTS "Allow affiliate click tracking" ON public.affiliate_clicks;
DROP POLICY IF EXISTS "Service can create boq items"    ON public.boq_items;
DROP POLICY IF EXISTS "Service can update boq items"    ON public.boq_items;
DROP POLICY IF EXISTS "Users can create boq jobs"       ON public.boq_jobs;
DROP POLICY IF EXISTS "Service can create payments"     ON public.payments;
DROP POLICY IF EXISTS "Users can create projects"       ON public.projects;

-- ============================================
-- 3. Pin the trigger function's search_path (flagged WARN:
--    function_search_path_mutable). Empty search_path is safe — NOW() resolves
--    from pg_catalog, which is always implicitly searched.
-- ============================================

ALTER FUNCTION public.update_updated_at_column() SET search_path = '';

-- Note (intentionally NOT changed): the `pg_trgm` extension lives in the public
-- schema (WARN: extension_in_public). Moving it risks the GIN trigram indexes on
-- materials (gin_trgm_ops) and is not the source of the security alert. Left in
-- place; revisit with care if hardening further.
