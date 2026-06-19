ALTER TABLE public.materials ADD COLUMN IF NOT EXISTS cached_product_name TEXT;
COMMENT ON COLUMN public.materials.cached_product_name IS
    'Display name of the best scraped product for this cache row (so cache hits show the real product, not the echoed search query).';
