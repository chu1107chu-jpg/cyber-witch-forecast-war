-- ============================================================
--  предсказания — DB schema
--  PostgreSQL / Supabase
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------
-- profiles
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username    TEXT,
    avatar_url  TEXT,
    lang        TEXT NOT NULL DEFAULT 'ru',
    role        TEXT NOT NULL DEFAULT 'user',   -- 'user' | 'admin'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- wallets
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wallets (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE UNIQUE,
    balance     BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- wallet_tx  (credit ledger)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wallet_tx (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    type             TEXT NOT NULL CHECK (type IN ('credit','debit')),
    amount           BIGINT NOT NULL CHECK (amount > 0),
    description      TEXT,
    idempotency_key  TEXT UNIQUE,
    ref_id           UUID,            -- FK to game_rounds / spins / etc.
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS wallet_tx_user_idx       ON public.wallet_tx (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS wallet_tx_idem_idx       ON public.wallet_tx (idempotency_key);

-- ------------------------------------------------------------
-- nft_items
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.nft_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    creator_id      UUID NOT NULL REFERENCES public.profiles(id),
    name            TEXT NOT NULL,
    description     TEXT,
    image_url       TEXT,
    metadata_url    TEXT,
    chain           TEXT NOT NULL DEFAULT 'internal',  -- 'internal'|'ton'|'solana'
    on_chain_id     TEXT,
    moderation_ok   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- nft_owners
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.nft_owners (
    nft_id      UUID NOT NULL REFERENCES public.nft_items(id) ON DELETE CASCADE,
    owner_id    UUID NOT NULL REFERENCES public.profiles(id),
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (nft_id, owner_id)
);

-- ------------------------------------------------------------
-- game_rounds  (guess-sign)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.game_rounds (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES public.profiles(id),
    ticker      TEXT NOT NULL,
    horizon     TEXT NOT NULL,          -- 't+1' | 't+20'
    stake       BIGINT NOT NULL,
    choice      TEXT NOT NULL,          -- 'up' | 'down'
    real_sign   TEXT,                   -- 'up' | 'down' (filled on resolve)
    win         BOOLEAN,
    payout      BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS game_rounds_user_idx ON public.game_rounds (user_id, created_at DESC);

-- ------------------------------------------------------------
-- spins
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.spins (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID NOT NULL REFERENCES public.profiles(id),
    game_id          TEXT NOT NULL DEFAULT 'utility_slot_v1',
    stake            BIGINT NOT NULL,
    bucket           TEXT NOT NULL,
    payout           BIGINT NOT NULL DEFAULT 0,
    server_seed_hash TEXT,
    client_nonce     TEXT,
    u                DOUBLE PRECISION,
    k                TEXT,
    near_miss        BOOLEAN NOT NULL DEFAULT FALSE,
    idempotency_key  TEXT UNIQUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS spins_user_idx  ON public.spins (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS spins_game_idx  ON public.spins (game_id, created_at DESC);

-- ------------------------------------------------------------
-- snake_rounds
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.snake_rounds (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES public.profiles(id),
    session_id      UUID NOT NULL DEFAULT uuid_generate_v4(),
    stake           BIGINT NOT NULL,
    catches         INT NOT NULL DEFAULT 0,
    payout          BIGINT NOT NULL DEFAULT 0,
    server_seed     TEXT,
    client_nonce    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS snake_rounds_user_idx ON public.snake_rounds (user_id, created_at DESC);

-- ------------------------------------------------------------
-- snake_catches  (per-ball log)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.snake_catches (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    round_id    UUID NOT NULL REFERENCES public.snake_rounds(id) ON DELETE CASCADE,
    ball_idx    INT  NOT NULL,
    color       TEXT NOT NULL,
    caught      BOOLEAN NOT NULL,
    multiplier  DOUBLE PRECISION NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------
-- game_configs  (RTP overrides, admin editable)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.game_configs (
    game_id     TEXT PRIMARY KEY,
    config_json JSONB NOT NULL,
    updated_by  UUID REFERENCES public.profiles(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- risk_limits
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.risk_limits (
    game_id             TEXT PRIMARY KEY REFERENCES public.game_configs(game_id),
    max_payout_per_spin BIGINT NOT NULL DEFAULT 10000,
    daily_loss_cap      BIGINT NOT NULL DEFAULT 100000,
    max_rtp             DOUBLE PRECISION NOT NULL DEFAULT 0.45,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- Trigger: update profiles.updated_at
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='profiles_updated_at') THEN
    CREATE TRIGGER profiles_updated_at BEFORE UPDATE ON public.profiles
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='wallets_updated_at') THEN
    CREATE TRIGGER wallets_updated_at BEFORE UPDATE ON public.wallets
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
END $$;
