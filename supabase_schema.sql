-- KETS permanent storage schema for Supabase/PostgreSQL
-- FIX: signal IDs such as BTC-SELL-1788687076633 and SCAN-GOLD-... are TEXT.
-- Run this entire file once in Supabase SQL Editor.
-- It safely converts legacy bigint IDs to text before creating indexes.

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

-- Migrate legacy installations whose id column was accidentally bigint.
do $$
declare
  signals_type text;
  history_type text;
begin
  select data_type into signals_type
  from information_schema.columns
  where table_schema='public' and table_name='signals' and column_name='id';

  if signals_type = 'bigint' then
    alter table public.signals alter column id type text using id::text;
  end if;

  select data_type into history_type
  from information_schema.columns
  where table_schema='public' and table_name='engine_history' and column_name='id';

  if history_type = 'bigint' then
    alter table public.engine_history alter column id type text using id::text;
  end if;
end $$;

create index if not exists signals_timestamp_idx on public.signals (timestamp_utc desc);
create index if not exists signals_asset_idx on public.signals (asset);
create index if not exists engine_history_timestamp_idx on public.engine_history (timestamp_utc desc);
create index if not exists engine_history_asset_idx on public.engine_history (asset);

alter table public.signals enable row level security;
alter table public.engine_history enable row level security;
