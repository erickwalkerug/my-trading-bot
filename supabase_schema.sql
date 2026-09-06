-- KETS permanent storage schema for Supabase/PostgreSQL
-- Run this once in Supabase SQL Editor.

create table if not exists public.signals (
  id text primary key,
  asset text not null,
  direction text not null,
  score numeric,
  market_price numeric,
  take_profit numeric,
  stop_loss numeric,
  expected_price_move numeric,
  expected_price_move_percent numeric,
  price_move numeric,
  price_move_pct numeric,
  market_move numeric,
  market_move_pct numeric,
  expected_move numeric,
  expected_move_pct numeric,
  current_price numeric,
  price numeric,
  entry numeric,
  estimated_duration text,
  classification text,
  interpretation text,
  timestamp text,
  source_timestamp_eat text,
  timestamp_utc timestamptz not null,
  status text default 'ACTIVE',
  created_at timestamptz default now()
);

create index if not exists signals_timestamp_idx on public.signals (timestamp_utc desc);
create index if not exists signals_asset_idx on public.signals (asset);

create table if not exists public.engine_history (
  id text primary key,
  asset text not null,
  symbol text,
  market_price numeric,
  candles integer,
  result text,
  status text,
  timestamp text,
  timestamp_utc timestamptz not null,
  direction text,
  score numeric,
  classification text,
  interpretation text,
  entry numeric,
  price numeric,
  current_price numeric,
  take_profit numeric,
  stop_loss numeric,
  price_move numeric,
  price_move_pct numeric,
  market_move numeric,
  market_move_pct numeric,
  expected_price_move numeric,
  expected_price_move_percent numeric,
  expected_move numeric,
  expected_move_pct numeric,
  estimated_duration text,
  created_at timestamptz default now()
);

create index if not exists engine_history_timestamp_idx on public.engine_history (timestamp_utc desc);
create index if not exists engine_history_asset_idx on public.engine_history (asset);

-- The bot uses the Supabase service-role key server-side, so RLS can remain enabled.
alter table public.signals enable row level security;
alter table public.engine_history enable row level security;

-- No public policies are created here. The website should use its own controlled
-- API/server or narrowly-scoped read policies if it reads Supabase directly.
