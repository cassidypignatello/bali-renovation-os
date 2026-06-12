ALTER TABLE boq_jobs
    ADD COLUMN IF NOT EXISTS compared_count INT,
    ADD COLUMN IF NOT EXISTS shopping_list_total DECIMAL(15,2);

COMMENT ON COLUMN boq_jobs.compared_count IS
    'Items in the savings comparison: priced AND contractor-supplied (owner-supply lines are labor rates, not comparable).';
COMMENT ON COLUMN boq_jobs.shopping_list_total IS
    'Estimated purchase cost of priced owner-supply items (market prices).';
