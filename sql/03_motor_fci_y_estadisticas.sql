-- ATLAS IA V4: ejecutar UNA VEZ luego del esquema 01 y la función 02.
-- Sin broker. FCI: suscripción ficticia ESTIMADA a un VCP posterior.
begin;
create table if not exists public.atlas_nav_intents (
 order_id uuid primary key references public.atlas_orders(id),
 baseline_date date not null,
 baseline_price numeric(22,6) not null check(baseline_price>0),
 fund_name text not null,
 created_at timestamptz not null default now()
);
create table if not exists public.atlas_equity_history (
 portfolio_id uuid not null references public.atlas_portfolios(id),
 observed_at timestamptz not null,
 cash_ars numeric(22,4) not null,
 holdings_ars numeric(22,4) not null,
 equity_ars numeric(22,4) not null,
 mep_ars numeric(22,6),
 equity_usd numeric(22,4),
 mep_source text,
 valuation_flags jsonb not null default '{}'::jsonb,
 primary key(portfolio_id,observed_at)
);
alter table public.atlas_nav_intents enable row level security;
alter table public.atlas_equity_history enable row level security;
revoke all on public.atlas_nav_intents,public.atlas_equity_history from anon,authenticated;
grant select,insert,update,delete on public.atlas_nav_intents,public.atlas_equity_history to service_role;
-- Secure atomic NAV fill. No instantaneous fills; note no guarantee of access to any fund.
create or replace function public.atlas_apply_nav_paper_fill(
 p_order_id uuid, p_quote_id bigint
) returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare
 o public.atlas_orders%rowtype;
 p public.atlas_portfolios%rowtype;
 q public.atlas_quotes%rowtype;
 intent public.atlas_nav_intents%rowtype;
 pos public.atlas_positions%rowtype;
 ins public.atlas_instruments%rowtype;
 amount numeric; nav numeric; quantity numeric; pnl numeric:=0;
begin
 select * into o from public.atlas_orders where id=p_order_id for update;
 if not found or o.status<>'PENDING' or o.profile<>'conservador' then
  return jsonb_build_object('ok',false,'reason','ORDEN_FCI_NO_PENDIENTE');end if;
 select * into intent from public.atlas_nav_intents where order_id=o.id;
 if not found then return jsonb_build_object('ok',false,'reason','SIN_INTENCION_FCI');end if;
 select * into p from public.atlas_portfolios where id=o.portfolio_id for update;
 if not p.simulation_only or not p.autonomy_enabled or not p.trading_enabled then
  return jsonb_build_object('ok',false,'reason','AUTONOMIA_INACTIVA');end if;
 select * into ins from public.atlas_instruments where id=o.instrument_id;
 if not found or ins.currency<>'ARS' or ins.asset_type<>'fondo' then
  return jsonb_build_object('ok',false,'reason','INSTRUMENTO_INCORRECTO');end if;
 select * into q from public.atlas_quotes where id=p_quote_id;
 if not found or q.instrument_id<>o.instrument_id or q.source_name not like 'compararfondos.com.ar /api/fondos%' then
  return jsonb_build_object('ok',false,'reason','VCP_FUENTE_INVALIDA');end if;
 -- El VCP tiene que ser de un día posterior al conocido al generar la orden.
 -- Y el motor debe haberlo observado después de colocarla.
 if (q.quoted_at at time zone 'America/Argentina/Buenos_Aires')::date <= intent.baseline_date
    or q.received_at <= o.placed_at or q.quoted_at > now()+interval '1 hour'
    or q.quoted_at < now()-interval '6 days' then
  return jsonb_build_object('ok',false,'reason','VCP_NO_POSTERIOR_O_DESACTUALIZADO');end if;
 nav:=q.price; quantity:=o.quantity;
 if nav<=0 or abs(nav/intent.baseline_price-1)>0.03 then
  return jsonb_build_object('ok',false,'reason','CAMBIO_VCP_ANORMAL_REVISAR');end if;
 if o.side='BUY' and nav>o.limit_price then return jsonb_build_object('ok',false,'reason','LIMITE_COMPRA');end if;
 if o.side='SELL' and nav<o.limit_price then return jsonb_build_object('ok',false,'reason','LIMITE_RESCATE');end if;
 amount:=round(quantity*nav,4);
 insert into public.atlas_positions(portfolio_id,instrument_id,profile,quantity,average_cost,realized_pnl)
 values(o.portfolio_id,o.instrument_id,o.profile,0,0,0)
 on conflict (portfolio_id,instrument_id,profile) do nothing;
 select * into pos from public.atlas_positions
 where portfolio_id=o.portfolio_id and instrument_id=o.instrument_id and profile=o.profile for update;
 if o.side='BUY' then
  if p.cash_ars<amount then return jsonb_build_object('ok',false,'reason','EFECTIVO_INSUFICIENTE');end if;
  update public.atlas_portfolios set cash_ars=cash_ars-amount where id=p.id;
  update public.atlas_positions
  set average_cost=(quantity*average_cost+amount)/(quantity+o.quantity),
      quantity=quantity+o.quantity,updated_at=now()
  where portfolio_id=o.portfolio_id and instrument_id=o.instrument_id and profile=o.profile;
 else
  if pos.quantity<quantity then return jsonb_build_object('ok',false,'reason','CUOTAPARTES_INSUFICIENTES');end if;
  pnl:=amount-quantity*pos.average_cost;
  update public.atlas_portfolios set cash_ars=cash_ars+amount where id=p.id;
  update public.atlas_positions set quantity=quantity-o.quantity,
    average_cost=case when quantity=o.quantity then 0 else average_cost end,
    realized_pnl=realized_pnl+pnl,updated_at=now()
  where portfolio_id=o.portfolio_id and instrument_id=o.instrument_id and profile=o.profile;
 end if;
 insert into public.atlas_fills(order_id,quote_id,filled_at,quantity,price,fee,slippage_pct,execution_method)
 values(o.id,q.id,q.received_at,quantity,nav,0,0,'estimated_subscription_at_later_published_NAV');
 insert into public.atlas_cash_ledger(portfolio_id,currency,amount,category,reference_id,memo)
 values(p.id,'ARS',case when o.side='BUY' then -amount else amount end,o.side,o.id,'FCI: suscripción/rescate ficticio a VCP posterior (no ejecución verificable)')
 on conflict(portfolio_id,category,reference_id) do nothing;
 update public.atlas_orders set status='FILLED',updated_at=now() where id=o.id;
 return jsonb_build_object('ok',true,'estimated',true,'side',o.side,'quantity',quantity,'nav',nav,'pnl',pnl);
end;$$;
revoke all on function public.atlas_apply_nav_paper_fill(uuid,bigint) from public,anon,authenticated;
grant execute on function public.atlas_apply_nav_paper_fill(uuid,bigint) to service_role;
commit;
