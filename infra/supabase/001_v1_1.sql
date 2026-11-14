-- ServeTrace v1.1: the one small store. Build prompt §8.1. Applied by hand, by Rahul.
--
-- Holds exactly two things:
--   usage_daily  anonymous counts per day. No time finer than a day, no IP, no user
--                agent, no coordinates, no affidavit fields, no case data of any kind.
--   leads        what a person typed into the /attorneys contact form, with consent.
--
-- Row-level security is on and there are no policies, so the public anon key can read or
-- write nothing. Only the server's service-role key (which bypasses RLS) is used.

create table if not exists usage_daily (
  day    date    not null,
  kind   text    not null,
  tier   text    not null default '',
  bucket text    not null default '',
  count  integer not null default 0,
  primary key (day, kind, tier, bucket)
);

create table if not exists leads (
  id           bigint generated always as identity primary key,
  created_day  date not null default current_date,
  name         text not null,
  email        text not null,
  organization text,
  role         text not null,
  message      text
);

alter table usage_daily enable row level security;
alter table leads enable row level security;
-- No policies: only the service-role key (bypasses RLS) can read or write.

-- Supabase grants anon and authenticated full table privileges by default, so with only
-- the lines above, RLS is the single thing between the public key and every lead's name
-- and email. Revoking the grants means switching RLS off by mistake still exposes nothing.
revoke all on table usage_daily from anon, authenticated;
revoke all on table leads from anon, authenticated;

create or replace function bump_usage(p_day date, p_kind text, p_tier text, p_bucket text)
returns void
language sql
security definer
set search_path = public
as $$
  insert into usage_daily (day, kind, tier, bucket, count)
  values (p_day, p_kind, p_tier, p_bucket, 1)
  on conflict (day, kind, tier, bucket) do update set count = usage_daily.count + 1;
$$;

-- A `security definer` function runs as its owner, and Postgres lets PUBLIC execute new
-- functions by default — so without these two lines anyone holding the public anon key
-- could call /rpc/bump_usage and inflate the counts, RLS notwithstanding.
revoke execute on function bump_usage(date, text, text, text) from public, anon, authenticated;
grant execute on function bump_usage(date, text, text, text) to service_role;

-- To delete one person's lead on request:
--   delete from leads where email = '<their address>';
