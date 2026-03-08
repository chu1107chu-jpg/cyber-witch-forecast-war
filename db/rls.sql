-- ============================================================
--  предсказания — Row Level Security (RLS)
--  Run AFTER schema.sql
-- ============================================================

-- Enable RLS on all user-facing tables
ALTER TABLE public.profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallets        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wallet_tx      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nft_items      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nft_owners     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.game_rounds    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spins          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.snake_rounds   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.snake_catches  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.game_configs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_limits    ENABLE ROW LEVEL SECURITY;

-- Helper: is the caller an admin?
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN LANGUAGE sql SECURITY DEFINER AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin'
  );
$$;

-- ============================================================
-- profiles
-- ============================================================
CREATE POLICY "profiles_select_own"
  ON public.profiles FOR SELECT
  USING (id = auth.uid() OR public.is_admin());

CREATE POLICY "profiles_update_own"
  ON public.profiles FOR UPDATE
  USING (id = auth.uid() OR public.is_admin())
  WITH CHECK (id = auth.uid() OR public.is_admin());

CREATE POLICY "profiles_insert_own"
  ON public.profiles FOR INSERT
  WITH CHECK (id = auth.uid());

-- ============================================================
-- wallets
-- ============================================================
CREATE POLICY "wallets_select_own"
  ON public.wallets FOR SELECT
  USING (user_id = auth.uid() OR public.is_admin());

-- Writes only via service role (backend API uses SERVICE_ROLE_KEY)
-- No INSERT/UPDATE/DELETE policy for anon/authenticated → backend bypasses RLS via service role

-- ============================================================
-- wallet_tx
-- ============================================================
CREATE POLICY "wallet_tx_select_own"
  ON public.wallet_tx FOR SELECT
  USING (user_id = auth.uid() OR public.is_admin());

-- ============================================================
-- nft_items  — public read, owner/admin write
-- ============================================================
CREATE POLICY "nft_items_select_all"
  ON public.nft_items FOR SELECT USING (TRUE);

CREATE POLICY "nft_items_insert_own"
  ON public.nft_items FOR INSERT
  WITH CHECK (creator_id = auth.uid() OR public.is_admin());

CREATE POLICY "nft_items_update_admin"
  ON public.nft_items FOR UPDATE
  USING (public.is_admin());

-- ============================================================
-- nft_owners
-- ============================================================
CREATE POLICY "nft_owners_select_all"
  ON public.nft_owners FOR SELECT USING (TRUE);

CREATE POLICY "nft_owners_insert_own"
  ON public.nft_owners FOR INSERT
  WITH CHECK (owner_id = auth.uid() OR public.is_admin());

-- ============================================================
-- game_rounds
-- ============================================================
CREATE POLICY "game_rounds_select_own"
  ON public.game_rounds FOR SELECT
  USING (user_id = auth.uid() OR public.is_admin());

-- ============================================================
-- spins
-- ============================================================
CREATE POLICY "spins_select_own"
  ON public.spins FOR SELECT
  USING (user_id = auth.uid() OR public.is_admin());

-- ============================================================
-- snake_rounds
-- ============================================================
CREATE POLICY "snake_rounds_select_own"
  ON public.snake_rounds FOR SELECT
  USING (user_id = auth.uid() OR public.is_admin());

CREATE POLICY "snake_catches_select_own"
  ON public.snake_catches FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.snake_rounds sr
      WHERE sr.id = snake_catches.round_id
        AND (sr.user_id = auth.uid() OR public.is_admin())
    )
  );

-- ============================================================
-- game_configs / risk_limits — admin only
-- ============================================================
CREATE POLICY "game_configs_select_all"
  ON public.game_configs FOR SELECT USING (TRUE);

CREATE POLICY "game_configs_write_admin"
  ON public.game_configs FOR ALL
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

CREATE POLICY "risk_limits_select_all"
  ON public.risk_limits FOR SELECT USING (TRUE);

CREATE POLICY "risk_limits_write_admin"
  ON public.risk_limits FOR ALL
  USING (public.is_admin())
  WITH CHECK (public.is_admin());
