-- Ejecutar UNA vez en SQL Editor, después del esquema 01 ya instalado.
-- Aplica la ejecución ficticia ATÓMICAMENTE para evitar compras sin descontar efectivo.
-- Nunca recibe claves de broker. La función es invocable solo por service_role.
create or replace function public.atlas_apply_paper_fill(
 p_order_id uuid, p_quote_id bigint, p_price numeric,
 p_fee_rate numeric default 0.005, p_slippage_rate numeric default 0.002
) returns jsonb language plpgsql security definer set search_path = public, pg_temp as $$
declare
 o public.atlas_orders%rowtype;
 p public.atlas_portfolios%rowtype;
 q public.atlas_quotes%rowtype;
 pos public.atlas_positions%rowtype;
 charge numeric; fees numeric; quantity numeric;
 pnl numeric := 0;
begin
 select * into o from public.atlas_orders where id=p_order_id for update;
 if not found or o.status <> 'PENDING' then return jsonb_build_object('ok',false,'reason','ORDEN_NO_PENDIENTE'); end if;
 select * into p from public.atlas_portfolios where id=o.portfolio_id for update;
 if not p.simulation_only or not p.trading_enabled or not p.autonomy_enabled then
  return jsonb_build_object('ok',false,'reason','AUTONOMIA_DESHABILITADA');
 end if;
 select * into q from public.atlas_quotes where id=p_quote_id;
 if not found or q.instrument_id <> o.instrument_id or q.quoted_at <= o.placed_at
 then return jsonb_build_object('ok',false,'reason','COTIZACION_INVALIDA_O_NO_POSTERIOR'); end if;
 if q.quoted_at < now()-interval '15 minutes' or q.quoted_at > now()+interval '1 minute' then
  return jsonb_build_object('ok',false,'reason','COTIZACION_VENCIDA');
 end if;
 if p_price<=0 or p_fee_rate<0 or p_fee_rate>0.05 or p_slippage_rate<0 or p_slippage_rate>0.05 then
  return jsonb_build_object('ok',false,'reason','PARAMETROS_INVALIDOS'); end if;
 if o.side='BUY' and p_price>o.limit_price then return jsonb_build_object('ok',false,'reason','LIMITE_COMPRA');end if;
 if o.side='SELL' and p_price<o.limit_price then return jsonb_build_object('ok',false,'reason','LIMITE_VENTA');end if;
 quantity:=o.quantity;
 -- solamente ARS para esta primera etapa; no conversiones USD ficticias inventadas
 if not exists(select 1 from public.atlas_instruments where id=o.instrument_id and currency='ARS') then
  return jsonb_build_object('ok',false,'reason','MONEDA_NO_HABILITADA'); end if;
 fees:=round(quantity*p_price*p_fee_rate,4);
 charge:=round(quantity*p_price,4);
 insert into public.atlas_positions(portfolio_id,instrument_id,profile,quantity,average_cost,realized_pnl)
 values(o.portfolio_id,o.instrument_id,o.profile,0,0,0)
 on conflict (portfolio_id,instrument_id,profile) do nothing;
 select * into pos from public.atlas_positions
 where portfolio_id=o.portfolio_id and instrument_id=o.instrument_id and profile=o.profile for update;
 if o.side='BUY' then
  if p.cash_ars<charge+fees then return jsonb_build_object('ok',false,'reason','SIN_EFECTIVO');end if;
  update public.atlas_portfolios set cash_ars=cash_ars-charge-fees where id=p.id;
  update public.atlas_positions
    set average_cost=case when quantity+o.quantity>0 then (quantity*average_cost+charge+fees)/(quantity+o.quantity) else 0 end,
        quantity=quantity+o.quantity,updated_at=now()
    where portfolio_id=o.portfolio_id and instrument_id=o.instrument_id and profile=o.profile;
 else
  if pos.quantity<quantity then return jsonb_build_object('ok',false,'reason','POSICION_INSUFICIENTE');end if;
  pnl:=charge-fees-quantity*pos.average_cost;
  update public.atlas_portfolios set cash_ars=cash_ars+charge-fees where id=p.id;
  update public.atlas_positions
    set quantity=quantity-o.quantity,average_cost=case when quantity=o.quantity then 0 else average_cost end,
        realized_pnl=realized_pnl+pnl, updated_at=now()
    where portfolio_id=o.portfolio_id and instrument_id=o.instrument_id and profile=o.profile;
 end if;
 insert into public.atlas_fills(order_id,quote_id,filled_at,quantity,price,fee,slippage_pct,execution_method)
 values(o.id,q.id,q.quoted_at,quantity,p_price,fees,p_slippage_rate,'estimated_from_delayed_public_data');
 insert into public.atlas_cash_ledger(portfolio_id,currency,amount,category,reference_id,memo)
 values(p.id,'ARS',case when o.side='BUY' then -charge-fees else charge-fees end,o.side,o.id,'Ejecución ficticia estimada')
 on conflict(portfolio_id,category,reference_id) do nothing;
 update public.atlas_orders set status='FILLED',updated_at=now() where id=o.id;
 return jsonb_build_object('ok',true,'side',o.side,'qty',quantity,'price',p_price,'fee',fees,'pnl',pnl);
end;$$;
revoke all on function public.atlas_apply_paper_fill(uuid,bigint,numeric,numeric,numeric) from public,anon,authenticated;
grant execute on function public.atlas_apply_paper_fill(uuid,bigint,numeric,numeric,numeric) to service_role;
-- El despliegue permanece DESACTIVADO hasta que habilites autonomía y trading en tu cartera.
select code, cash_ars, autonomy_enabled, trading_enabled from public.atlas_portfolios where code='ATLAS-DEMO-001';
