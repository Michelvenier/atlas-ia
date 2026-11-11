-- ATLAS V5: depósitos a plazo ficticios. Es independiente de la migración 03.
-- Ejecutar una sola vez sobre la base existente. No reinicia capital ni posiciones.
begin;
create table if not exists public.atlas_term_deposits (
 id uuid primary key default gen_random_uuid(),
 portfolio_id uuid not null references public.atlas_portfolios(id),
 bank text not null,
 product text,
 principal numeric(22,4) not null check(principal>0),
 tea_pct numeric(12,6) not null check(tea_pct between 1 and 100),
 started_at timestamptz not null default now(),
 maturity_at timestamptz not null,
 rate_date date not null,
 source_url text not null,
 restrictions text,
 status text not null default 'ACTIVE' check(status in ('ACTIVE','MATURED')),
 matured_at timestamptz,
 interest_paid numeric(22,4) not null default 0,
 unique (portfolio_id,started_at)
);
create index if not exists atlas_term_active on public.atlas_term_deposits(portfolio_id,status,maturity_at);
create table if not exists public.atlas_signal_outcomes (
 decision_id uuid not null references public.atlas_decisions(id),
 horizon_days integer not null check (horizon_days in (5,20)),
 observed_at timestamptz not null,
 baseline_price numeric(22,6) not null,
 observed_price numeric(22,6) not null,
 return_pct numeric(14,6) not null,
 direction_correct boolean,
 primary key(decision_id,horizon_days)
);
alter table public.atlas_signal_outcomes enable row level security;
revoke all on public.atlas_signal_outcomes from anon,authenticated;
grant select,insert,update on public.atlas_signal_outcomes to service_role;
alter table public.atlas_term_deposits enable row level security;
revoke all on public.atlas_term_deposits from anon,authenticated;
grant select,insert,update on public.atlas_term_deposits to service_role;

create or replace function public.atlas_open_paper_term(
 p_portfolio_id uuid,p_bank text,p_product text,p_amount numeric,
 p_tea numeric,p_rate_date date,p_source text,p_restrictions text
) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare p public.atlas_portfolios%rowtype;id uuid;used numeric;fci_used numeric;
begin
 select * into p from public.atlas_portfolios where id=p_portfolio_id for update;
 if not found or not p.simulation_only or not p.autonomy_enabled or not p.trading_enabled then
  return jsonb_build_object('ok',false,'reason','AUTONOMIA_INACTIVA');end if;
 if p_amount<50000 or p_amount>200000 or p_tea<1 or p_tea>100 or
    p_rate_date> (now() at time zone 'America/Argentina/Buenos_Aires')::date or
    p_rate_date < (now() at time zone 'America/Argentina/Buenos_Aires')::date - 3 or
    p_source <> 'https://api.bcra.gob.ar/transparencia/v1.0/PlazosFijos' then
   return jsonb_build_object('ok',false,'reason','OFERTA_O_MONTO_INVALIDOS');end if;
 select coalesce(sum(principal),0) into used from public.atlas_term_deposits
 where portfolio_id=p.id and status='ACTIVE';
 select coalesce(sum(pos.quantity*pos.average_cost),0) into fci_used
 from public.atlas_positions pos join public.atlas_instruments i on i.id=pos.instrument_id
 where pos.portfolio_id=p.id and pos.profile='conservador' and i.asset_type='fondo';
 if used + fci_used + p_amount>p.initial_cash*.60 then
  return jsonb_build_object('ok',false,'reason','LIMITE_PERFIL_CONSERVADOR_60_PCT');end if;
 if used + p_amount>p.initial_cash*.25 then
  return jsonb_build_object('ok',false,'reason','LIMITE_PLAZO_FIJO_25_PCT');end if;
 if exists(select 1 from public.atlas_term_deposits where portfolio_id=p.id and status='ACTIVE'
    and (started_at at time zone 'America/Argentina/Buenos_Aires')::date=(now() at time zone 'America/Argentina/Buenos_Aires')::date) then
  return jsonb_build_object('ok',false,'reason','YA_HAY_PLAZO_FIJO_HOY');end if;
 if p.cash_ars<p_amount then return jsonb_build_object('ok',false,'reason','SIN_EFECTIVO');end if;
 insert into public.atlas_term_deposits(portfolio_id,bank,product,principal,tea_pct,
     maturity_at,rate_date,source_url,restrictions)
 values(p.id,left(p_bank,200),left(p_product,200),p_amount,p_tea,now()+interval '30 days',p_rate_date,p_source,left(p_restrictions,300)) returning atlas_term_deposits.id into id;
 update public.atlas_portfolios set cash_ars=cash_ars-p_amount where atlas_portfolios.id=p.id;
 insert into public.atlas_cash_ledger(portfolio_id,currency,amount,category,reference_id,memo)
 values(p.id,'ARS',-p_amount,'BUY',id,'Plazo fijo simulado, banco '||left(p_bank,100));
 insert into public.atlas_audit_events(portfolio_id,event_type,message,payload)
 values(p.id,'TERM_OPEN','Plazo fijo ficticio constituido con TEA informativa del BCRA',
 jsonb_build_object('deposit_id',id,'bank',p_bank,'tea',p_tea,'amount',p_amount,'rate_date',p_rate_date,'matures_in_days',30));
 return jsonb_build_object('ok',true,'deposit_id',id,'amount',p_amount);
end;$$;

create or replace function public.atlas_mature_paper_terms(p_portfolio_id uuid)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare p public.atlas_portfolios%rowtype;r public.atlas_term_deposits%rowtype;
 interest numeric;num integer:=0;
begin
 select * into p from public.atlas_portfolios where id=p_portfolio_id for update;
 if not found or not p.simulation_only then return jsonb_build_object('ok',false);end if;
 for r in select * from public.atlas_term_deposits where portfolio_id=p.id and status='ACTIVE'
  and maturity_at<=now() for update loop
  interest:=round(r.principal*(power(1+r.tea_pct/100,30.0/365.0)-1),4);
  update public.atlas_term_deposits set status='MATURED',matured_at=now(),interest_paid=interest where id=r.id;
  update public.atlas_portfolios set cash_ars=cash_ars+r.principal+interest where id=p.id;
  insert into public.atlas_cash_ledger(portfolio_id,currency,amount,category,reference_id,memo)
   values(p.id,'ARS',r.principal+interest,'SELL',r.id,'Vencimiento plazo fijo simulado, incluye intereses');
  insert into public.atlas_audit_events(portfolio_id,event_type,message,payload)
   values(p.id,'TERM_MATURED','Plazo fijo ficticio al vencimiento',jsonb_build_object('deposit_id',r.id,'interest',interest));
  num:=num+1;
 end loop;
 return jsonb_build_object('ok',true,'matured',num);
end;$$;
revoke all on function public.atlas_open_paper_term(uuid,text,text,numeric,numeric,date,text,text) from public,anon,authenticated;
revoke all on function public.atlas_mature_paper_terms(uuid) from public,anon,authenticated;
grant execute on function public.atlas_open_paper_term(uuid,text,text,numeric,numeric,date,text,text) to service_role;
grant execute on function public.atlas_mature_paper_terms(uuid) to service_role;
commit;
