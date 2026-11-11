"""ATLAS IA: motor de paper trading, sin cuentas de broker.
Publica snapshot público SOLO con información ficticia.
La compra usa un precio posterior a una orden, no el último precio al generarla.
Yahoo chart es fuente gratuita NO certificada; ejecuciones son estimaciones.
"""
import os, json, time, math, statistics, datetime as dt, urllib.parse, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import exchange_calendars as xc
from .research import dynamic_catalog, local_watch_catalog, decision_committee
from .conservative import selected_funds, nav_quote_timestamp, conservative_window, NAV_SOURCE

TZ=ZoneInfo('America/Argentina/Buenos_Aires'); UTC=dt.timezone.utc
ROOT=Path(__file__).resolve().parents[1]
CODE='ATLAS-DEMO-001'
# Conservador: solo efectivo hasta disponer de precios de renta fija/ON/cauciones.
UNIVERSE={
 'SPY.BA':('SPY CEDEAR','cedear','moderado',0.28),
 'MSFT.BA':('Microsoft CEDEAR','cedear','moderado',0.28),
 'AAPL.BA':('Apple CEDEAR','cedear','moderado',0.28),
 'YPFD.BA':('YPF','accion','agresivo',0.48),
 'GGAL.BA':('Galicia','accion','agresivo',0.48),
 'PAMP.BA':('Pampa Energía','accion','agresivo',0.48),
}
BUY_SCORE=78
QUOTE_MAX_AGE_S=900
FEE=0.005
SLIPPAGE=0.002
MAX_PER_EMITTER=0.08
MAX_NEW_PER_RUN=1
MAX_ORDER_BY_PROFILE={'conservador':400000,'moderado':300000,'agresivo':200000}
# Instrumentos adicionales para OBSERVACIÓN. No autorizan compras nuevas.
WATCH_ONLY={
 'BMA.BA':('Banco Macro','XBUE','ARS','finanzas'),
 'ALUA.BA':('Aluar','XBUE','ARS','industria'),
 'TXAR.BA':('Ternium Argentina','XBUE','ARS','industria'),
 'XOM.BA':('ExxonMobil CEDEAR','XBUE','ARS','petroleo'),
 'NVDA.BA':('Nvidia CEDEAR','XBUE','ARS','tecnologia'),
 'AMZN.BA':('Amazon CEDEAR','XBUE','ARS','tecnologia'),
 'SPY':('SPDR S&P 500 ETF','XNYS','USD','mercado_global'),
 'XLE':('Energy Select Sector ETF','XNYS','USD','petroleo'),
 'AAPL':('Apple EEUU','XNAS','USD','tecnologia'),
 'MSFT':('Microsoft EEUU','XNAS','USD','tecnologia'),
 'XOM':('ExxonMobil EEUU','XNYS','USD','petroleo'),
}
# Suplemento defensivo de feriados excepcionales ya confirmados, no sustituye un feed oficial.
KNOWN_BYMA_CLOSED={'2026-11-09','2026-11-10'}
# 11/11/2026: BYMA negocia con reglas especiales de liquidación.
# ATLAS no modela T+1 para CEDEAR: no los ejecuta ese día.
SPECIAL_CEDEAR_T1_ONLY={'2026-11-11'}
LOCAL_SESSION_START=dt.time(10,30)
LOCAL_SESSION_END=dt.time(18,0)



def iso_now():return dt.datetime.now(UTC).isoformat()
def ts_parse(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def as_float(v):return float(v or 0)

class DB:
 def __init__(self):
  base=os.environ.get('SUPABASE_URL','').rstrip('/')
  key=os.environ.get('SUPABASE_SECRET_KEY','')
  if not base or not key: raise RuntimeError('Faltan SUPABASE_URL o SUPABASE_SECRET_KEY: no se ejecutan órdenes')
  if not base.startswith('https://'):raise RuntimeError('URL Supabase debe ser HTTPS')
  self.base=base+'/rest/v1';self.s=requests.Session()
  self.s.headers.update({'apikey':key,'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 def req(self,verb,table,params=None,data=None,prefer=None):
  h={'Prefer':prefer} if prefer else {}
  r=self.s.request(verb,self.base+'/'+table,params=params,json=data,headers=h,timeout=22)
  if not r.ok:raise RuntimeError(f'Supabase {table} HTTP {r.status_code}: {r.text[:400]}')
  return r.json() if r.content else []
 def get(self,t,**p):return self.req('GET',t,{'select':'*',**p})
 def insert(self,t,obj):return self.req('POST',t,data=obj,prefer='return=representation')
 def patch(self,t,params,obj):return self.req('PATCH',t,params=params,data=obj,prefer='return=representation')
 def upsert(self,t,objs,conflict):return self.req('POST',t,params={'on_conflict':conflict},data=objs,prefer='resolution=merge-duplicates,return=representation')
 def rpc(self,name,data):return self.req('POST','rpc/'+name,data=data)


def fetch_chart(symbol,interval,span):
 url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='')
 r=requests.get(url,params={'interval':interval,'range':span,'includePrePost':'false'},headers={'User-Agent':'Mozilla/5.0 (compatible; ATLASPaper/1.0)'},timeout=18)
 r.raise_for_status();doc=r.json()['chart'];obj=doc['result'][0]
 quotes=obj['indicators']['quote'][0]
 points=[]
 for j,t in enumerate(obj.get('timestamp') or []):
  p=quotes['close'][j]
  if isinstance(p,(int,float)) and math.isfinite(p) and p>0:
   points.append((dt.datetime.fromtimestamp(t,UTC),float(p)))
 return points


def analysis(points):
 vals=[p[1] for p in points]
 if len(vals)<55:raise ValueError('Menos de 55 cierres válidos')
 close=vals[-1];ma20=statistics.mean(vals[-20:]);ma50=statistics.mean(vals[-50:])
 changes=[vals[i]-vals[i-1] for i in range(1,len(vals))]
 g=sum(max(x,0) for x in changes[-14:])/14
 l=sum(max(-x,0) for x in changes[-14:])/14
 rsi=100 if l==0 else 100-100/(1+g/l)
 returns=[math.log(vals[i]/vals[i-1]) for i in range(1,len(vals))]
 vol=statistics.stdev(returns[-30:])*math.sqrt(252)
 score=50+(18 if close>ma20 else -18)+(12 if ma20>ma50 else -12)+(8 if 35<=rsi<=65 else -9 if rsi>75 else 0)+(-12 if vol>.55 else -6 if vol>.35 else 6)
 score=max(0,min(100,int(score)))
 return {'score':score,'last_close':round(close,4),'sma20':round(ma20,4),'sma50':round(ma50,4),'rsi':round(rsi,2),'vol':round(vol,4),'date':points[-1][0].date().isoformat()}


def session_open(now):
 """Validación restrictiva; no representa permisos de cada plazo de liquidación."""
 local=now.astimezone(TZ)
 day=local.date().isoformat()
 if local.weekday()>=5 or day in KNOWN_BYMA_CLOSED:return False
 if day in SPECIAL_CEDEAR_T1_ONLY:
  # Apertura local confirmada pero con restricciones: validación horaria adicional.
  return LOCAL_SESSION_START<=local.time().replace(tzinfo=None)<LOCAL_SESSION_END
 try:
  cal=xc.get_calendar('XBUE')
  return bool(cal.is_open_on_minute(pd.Timestamp(now).floor('min')))
 except Exception:return False

def instrument_session_allowed(symbol,now):
 """No asumir que un CEDEAR T+0 se puede operar en una rueda T+1."""
 if not session_open(now):return False,'MERCADO_CERRADO'
 if now.astimezone(TZ).date().isoformat() in SPECIAL_CEDEAR_T1_ONLY and symbol.endswith('.BA') and symbol in {s for s,(n,t,p,v) in UNIVERSE.items() if t=='cedear'}:
  return False,'CEDEAR_T1_SIN_SIMULADOR_DE_LIQUIDACION'
 return True,'SESION_ADMITIDA'

def valid_intraday_quote(q,now):
 if not q:return False,'SIN_PRECIO'
 t,p=q[-1]
 age=(now-t).total_seconds()
 if not (0<=age<=QUOTE_MAX_AGE_S):return False,'PRECIO_ANTIGUO'
 try:
  if now.astimezone(TZ).date().isoformat() in SPECIAL_CEDEAR_T1_ONLY:
   local_tick=t.astimezone(TZ)
   if local_tick.date()!=now.astimezone(TZ).date() or not (LOCAL_SESSION_START<=local_tick.time()<LOCAL_SESSION_END):
    return False,'COTIZACION_FUERA_DE_RUEDA'
  else:
   cal=xc.get_calendar('XBUE')
   if not cal.is_open_on_minute(pd.Timestamp(t).floor('min')):return False,'COTIZACION_FUERA_DE_RUEDA'
 except Exception:return False,'CALENDARIO_NO_DISPONIBLE'
 return True,'VALIDO_CON_DEMORA_POTENCIAL'


NEWS_TOPICS=[
 ('Argentina','macroeconomia','Argentina inflación BCRA tasa política monetaria dólar MEP reservas'),
 ('Argentina','politica','Argentina congreso ejecutivo presupuesto impuestos regulación economía'),
 ('Argentina','deuda','Argentina bonos deuda soberana AL30 GD30 licitación letras tesoro'),
 ('Argentina','obligaciones negociables','obligaciones negociables emisiones CNV vencimientos empresas argentina'),
 ('Argentina','fondos','fondos comunes inversión CAFCI rescates cuotapartes argentina'),
 ('Argentina','energia','YPF Vaca Muerta petróleo gas energía Argentina'),
 ('Argentina','bancos','bancos argentina balances riesgo crediticio liquidez'),
 ('Argentina','agro','argentina soja maíz trigo exportaciones retenciones'),
 ('Estados Unidos','monetaria','Federal Reserve rates inflation CPI employment Treasury'),
 ('Estados Unidos','empresas','US corporate earnings guidance quarterly filings SEC'),
 ('Estados Unidos','tecnologia','Nvidia Microsoft Apple Amazon artificial intelligence earnings'),
 ('Estados Unidos','energia','US crude oil gas inventories shale energy companies'),
 ('Estados Unidos','bonos','US treasury yields bonds yield curve credit spreads'),
 ('Global','petroleo','Brent WTI oil OPEC supply production geopolitics'),
 ('Global','gas','natural gas LNG exports global energy prices'),
 ('Global','tecnologia','semiconductors chip manufacturing Nvidia TSMC ASML'),
 ('Global','finanzas','global stocks equity market volatility risk credit'),
 ('Global','geopolitica','trade sanctions conflicts tariffs shipping energy risk'),
 ('China','economia','China property stimulus industrial production consumption demand'),
 ('Brasil','economia','Brasil Selic fiscal real bolsa Petrobras Vale'),
 ('Europa','macroeconomia','European Central Bank inflation rates eurozone'),
 ('Europa','energia','Europe natural gas electricity energy prices'),
 ('Medio Oriente','petroleo','Middle East oil supply OPEC crude geopolitical risk'),
 ('India','economia','India economy growth monetary policy energy demand'),
 ('Global','metales','copper gold lithium mining commodity prices'),
 ('Global','salud','healthcare pharma companies earnings drugs regulation'),
]

def news_feed(now):
 # Rotación de temas a lo largo del día. Recoge noticias aunque BYMA no tenga rueda.
 # No se utilizan titulares como reglas automáticas de compra/venta.
 slot=(now.astimezone(TZ).hour*4+now.minute//15)%len(NEWS_TOPICS)
 major=now.astimezone(TZ).hour in (8,12,17,19) and now.astimezone(TZ).minute<40
 topics=[NEWS_TOPICS[(slot+i*5)%len(NEWS_TOPICS)] for i in range(5 if major else 2)]
 out=[];seen=set();errors=[]
 for country,sector,query in topics:
  try:
   url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query+' when:2d','hl':'es-419','gl':'AR','ceid':'AR:es-419'})
   r=requests.get(url,timeout=15,headers={'User-Agent':'Mozilla/5.0'});r.raise_for_status()
   root=ET.fromstring(r.content)
   for n in root.findall('.//item')[:12]:
    link=n.findtext('link') or ''
    if not link.startswith('https://') or link in seen:continue
    seen.add(link)
    date_str=n.findtext('pubDate') or ''
    try:pub=parsedate_to_datetime(date_str).astimezone(UTC).isoformat()
    except Exception:pub=now.isoformat()
    out.append({'title':(n.findtext('title') or '')[:500], 'article_url':link,'publisher':n.findtext('source') or 'Google News', 'published_at':pub,'summary':'Titular recogido automáticamente; contenido no verificado. No utilizado como señal de compra.','country':country,'sector':sector,'metadata':{'source':'Google News RSS','query':query,'retrieved_at':now.isoformat()}})
  except Exception as e:errors.append(f'{country}/{sector}: {str(e)[:90]}')
 return out,errors


def position_map(db,pid):
 positions=db.get('atlas_positions',portfolio_id='eq.'+pid)
 return {(x['instrument_id'],x['profile']):x for x in positions}


def record_event(db,pid,kind,msg,payload=None):
 db.insert('atlas_audit_events',{'portfolio_id':pid,'event_type':kind,'message':msg[:800],'payload':payload or {}})


def fill_pending(db,pid,now,latest):
 orders=db.get('atlas_orders',portfolio_id='eq.'+pid,status='eq.PENDING')
 for order in orders:
  try:
   if order.get('expires_at') and now>=ts_parse(order['expires_at']):
    db.patch('atlas_orders',{'id':'eq.'+order['id'],'status':'eq.PENDING'},{'status':'EXPIRED','updated_at':iso_now(),'rejection_reason':'Orden expirada antes de obtener cotización posterior'})
    continue
   ins=db.get('atlas_instruments',id='eq.'+order['instrument_id'])[0]
   if ins['asset_type']=='fondo':continue
   sym=ins['symbol'];q=latest.get(sym)
   allowed,session_reason=instrument_session_allowed(sym,now)
   if not allowed:continue
   ok,why=valid_intraday_quote(q,now)
   if not ok:continue
   quote_time,price=q[-1]
   if quote_time <= ts_parse(order['placed_at']):continue
   if order.get('expires_at') and now>=ts_parse(order['expires_at']):
    db.patch('atlas_orders',{'id':'eq.'+order['id'],'status':'eq.PENDING'},{'status':'EXPIRED','updated_at':iso_now(),'rejection_reason':'Expiró sin cotización posterior válida'})
    continue
   # Ejecutar limit BUY si valor estimado <= límite; SELL si >= límite
   estimate=price*(1+SLIPPAGE if order['side']=='BUY' else 1-SLIPPAGE)
   if order['side']=='BUY' and estimate>as_float(order['limit_price']):continue
   if order['side']=='SELL' and estimate<as_float(order['limit_price']):continue
   rec=db.upsert('atlas_quotes',[{'instrument_id':ins['id'],'quoted_at':quote_time.isoformat(),'price':price,'source_name':'Yahoo Finance chart (potencialmente demorado)','delayed':True}], 'instrument_id,quoted_at,source_name')[0]
   result=db.rpc('atlas_apply_paper_fill',{'p_order_id':order['id'],'p_quote_id':rec['id'],'p_price':round(estimate,6),'p_fee_rate':FEE,'p_slippage_rate':SLIPPAGE})
   record_event(db,pid,'SIMULATED_FILL','Ejecución hipotética, no verificable en bolsa',{'order':order['id'],'estimated_price':estimate,'result':result})
  except Exception as ex:
   record_event(db,pid,'FILL_ERROR','La orden no se ejecutó: '+str(ex)[:250],{'order_id':order['id']})


def create_order(db,pid,ins,profile,side,qty,limit,reason,metrics,now):
 if qty<=0:return
 dec=db.insert('atlas_decisions',{'portfolio_id':pid,'instrument_id':ins['id'],'profile':profile,'action':'comprar' if side=='BUY' else 'vender','rationale':reason,'risk_result':'aprobado','risk_checks':metrics})[0]
 exp=now+dt.timedelta(minutes=45)
 obj={'portfolio_id':pid,'decision_id':dec['id'],'instrument_id':ins['id'],'profile':profile,'side':side,'quantity':qty,'limit_price':round(limit,6),'expires_at':exp.isoformat(),'client_order_key':f'{now.date()}-{ins["symbol"]}-{side}-{profile}'}
 try:order=db.insert('atlas_orders',obj)[0]
 except Exception as ex:
  if 'duplicate key' in str(ex).lower():return
  raise
 record_event(db,pid,'ORDER_PENDING',f'{side} {qty} {ins["symbol"]}: orden ficticia pendiente de observación posterior',{'limit':limit,'order':order['id']})


def mep_quote(now):
 """For valuation only: never authorizes USD trades."""
 try:
  r=requests.get('https://dolarapi.com/v1/dolares/bolsa',timeout=12,headers={'User-Agent':'ATLAS-IA/4.0'})
  r.raise_for_status();data=r.json();rate=as_float(data.get('venta'))
  stamp=ts_parse(data['fechaActualizacion'])
  age=(now-stamp).total_seconds()
  if not 0<=age<=36*3600 or rate<=0:raise ValueError('Dólar MEP ausente o vencido')
  return {'rate':rate,'as_of':stamp.isoformat(),'source':'DolarApi.com /v1/dolares/bolsa (venta, informativo)'}
 except Exception as exc:return {'rate':None,'reason':str(exc)[:120]}


def store_nav_observations(db,now,market_open,log):
 """Validate NAV classes; synchronize current NAV *without* interpreting it as a fill."""
 try:
  resp=requests.get('https://compararfondos.com.ar/api/fondos',timeout=18,headers={'User-Agent':'ATLAS-IA-Paper/4.0'});resp.raise_for_status();doc=resp.json()
  # A non-tradable day cannot create new subscription intents.
  rueda=doc.get('rueda') or {}
  if rueda.get('habil') is False:market_open=False
  age=doc.get('age_min')
  if age is not None and as_float(age)>180:raise ValueError('API FCI sin actualización reciente: más de 180 minutos')
  candidates=selected_funds(doc,now.astimezone(TZ))
  pid=db.get('atlas_portfolios',code='eq.'+CODE)[0]['id']
  held={x['instrument_id'] for x in db.get('atlas_positions',portfolio_id='eq.'+pid) if x['profile']=='conservador' and as_float(x['quantity'])>0}
  pending={x['instrument_id'] for x in db.get('atlas_orders',portfolio_id='eq.'+pid,status='eq.PENDING') if x['profile']=='conservador'}
  must_track=held|pending
  instruments=db.get('atlas_instruments',exchange='eq.CAFCI')
  tracked_symbols={i['symbol'] for i in instruments if i['id'] in must_track}
  funds=list({f['symbol']:f for f in (candidates[:35]+[f for f in candidates if f['symbol'] in tracked_symbols])}.values())
  by_symbol={}
  for f in funds:
   ins=db.upsert('atlas_instruments',[{'symbol':f['symbol'],'exchange':'CAFCI','currency':'ARS','name':f['name'],'asset_type':'fondo','enabled':True}], 'symbol,exchange,currency')[0]
   qtime=nav_quote_timestamp(f['date'])
   db.upsert('atlas_quotes',[{'instrument_id':ins['id'],'quoted_at':qtime.isoformat(), 'price':f['nav'],'source_name':NAV_SOURCE,'delayed':True}], 'instrument_id,quoted_at,source_name')
   by_symbol[f['symbol']]={'info':f,'instrument':ins}
  return by_symbol,market_open
 except Exception as exc:
  log.append({'conservative_feed':'FCI no disponible: '+str(exc)[:160]})
  return {},False


def fill_pending_nav(db,pid,now,funds,logs):
 """Fill is an explicitly hypothetical subscription at the next known NAV date."""
 orders=db.get('atlas_orders',portfolio_id='eq.'+pid,status='eq.PENDING')
 for order in orders:
  try:
   instrument=db.get('atlas_instruments',id='eq.'+order['instrument_id'])[0]
   if instrument.get('asset_type')!='fondo':continue
   if order.get('expires_at') and now>=ts_parse(order['expires_at']):
    db.patch('atlas_orders',{'id':'eq.'+order['id'],'status':'eq.PENDING'},{'status':'EXPIRED','updated_at':iso_now(),'rejection_reason':'No se publicó un VCP posterior antes del vencimiento'})
    record_event(db,pid,'FCI_ORDER_EXPIRED','Suscripción FCI no simulada: falta VCP posterior',{'order_id':order['id']})
    continue
   data=funds.get(instrument['symbol'])
   if not data:continue
   f=data['info'];quote=db.get('atlas_quotes',instrument_id='eq.'+instrument['id'],quoted_at='eq.'+nav_quote_timestamp(f['date']).isoformat(),source_name='eq.'+NAV_SOURCE,limit='1')
   if not quote:continue
   result=db.rpc('atlas_apply_nav_paper_fill',{'p_order_id':order['id'],'p_quote_id':quote[0]['id']})
   if result.get('ok'):
    record_event(db,pid,'FCI_ESTIMATED_SUBSCRIPTION','Suscripción/rescate FCI ficticio al siguiente VCP; disponibilidad y corte NO verificados',{'order_id':order['id'],'result':result})
   elif result.get('reason') not in ('VCP_NO_POSTERIOR_O_DESACTUALIZADO','AUTONOMIA_INACTIVA'):
    logs.append({'fci_fill':instrument['symbol'],'reason':result.get('reason')})
  except Exception as ex:logs.append({'fci_fill_error':str(ex)[:150]})


def consider_nav_subscription(db,pid,now,funds,market_open,logs):
 """One small subscription intent per date, only after explicit checks."""
 reasons=[]
 if not conservative_window(now,market_open):return 'Fuera de ventana ficticia de suscripción o sin rueda validada'
 port=db.get('atlas_portfolios',code='eq.'+CODE)[0]
 if not (port['autonomy_enabled'] and port['trading_enabled']):return 'Autonomía deshabilitada'
 alloc={x['profile']:as_float(x['target_pct'])/100 for x in db.get('atlas_allocations',portfolio_id='eq.'+pid)}
 max_budget=as_float(port['initial_cash'])*alloc.get('conservador',0)
 pos=position_map(db,pid)
 fci_ins={x['id']:x for x in db.get('atlas_instruments',exchange='eq.CAFCI')}
 positions=[(k,v) for k,v in pos.items() if k[1]=='conservador' and as_float(v['quantity'])>0]
 committed=sum(as_float(x['quantity'])*as_float(x['average_cost']) for _,x in positions)
 pending=db.get('atlas_orders',portfolio_id='eq.'+pid,status='eq.PENDING')
 if pending:return 'Hay órdenes pendientes; se evita comprometer saldo dos veces'
 if committed>=max_budget:return 'Perfil conservador ya alcanzó su asignación'
 if not funds:return 'No hay fondos de liquidez que superen los filtros verificables'
 # Fund NAV is never an executable order book. Buy max 400k, maintain liquidity.
 candidate_list=[x for x in funds.values() if x['info'].get('buy_eligible')]
 candidate_list.sort(key=lambda v:(-v['info']['r30'],v['info']['symbol']))
 for candidate in candidate_list:
  f=candidate['info'];ins=candidate['instrument']
  invested_here=sum(as_float(v['quantity'])*as_float(v['average_cost']) for (iid,_),v in positions if iid==ins['id'])
  active_funds={iid for (iid,_),v in positions}
  active_managers={entry['info'].get('manager') for entry in funds.values() if entry['instrument']['id'] in active_funds}
  if ins['id'] not in active_funds and f.get('manager') in active_managers:continue
  if len(active_funds)>=5 and ins['id'] not in active_funds:continue
  if invested_here>=min(1200000,as_float(port['initial_cash'])*0.12):continue
  cap=min(400000,max_budget-committed,1200000-invested_here,as_float(port['cash_ars'])*0.90)
  if cap<50000:continue
  qty=round(cap/(f['nav']*1.02),6)
  if qty<=0:continue
  rationale=(f"FCI money market ARS: VCP {f['nav']} del {f['date']}; retorno 30d "
             f"{f['r30']}% histórico NO garantizado. Orden ficticia al VCP de una fecha POSTERIOR. "
             "Corte horario, disponibilidad por broker y rescate no verificados.")
  checks={'type':'NAV_NEXT_PUBLICATION','base_nav_date':str(f['date']),'base_nav':f['nav'],
          'max_order_ars':cap,'max_fund_ars':1200000,'source':NAV_SOURCE,'no_actual_execution':True}
  dec=db.insert('atlas_decisions',{'portfolio_id':pid,'instrument_id':ins['id'],'profile':'conservador','action':'comprar','rationale':rationale,'risk_result':'aprobado','risk_checks':checks})[0]
  obj={'portfolio_id':pid,'decision_id':dec['id'],'instrument_id':ins['id'],'profile':'conservador','side':'BUY',
       'quantity':qty,'limit_price':round(f['nav']*1.03,6),'expires_at':(now+dt.timedelta(days=8)).isoformat(),
       'client_order_key':f'{now.astimezone(TZ).date()}-{ins["id"]}-BUY-conservador-NAV'}
  try:order=db.insert('atlas_orders',obj)[0]
  except Exception as ex:
   if 'duplicate' in str(ex).lower():return 'Ya se evaluó ese fondo hoy'
   raise
  try:db.insert('atlas_nav_intents',{'order_id':order['id'],'baseline_date':str(f['date']), 'baseline_price':f['nav'],'fund_name':f['name']})
  except Exception:
   db.patch('atlas_orders',{'id':'eq.'+order['id'],'status':'eq.PENDING'},{'status':'REJECTED','updated_at':iso_now(),'rejection_reason':'No se pudo crear intención NAV'})
   raise
  record_event(db,pid,'FCI_PENDING_NAV',f"Suscripción ficticia propuesta de {f['name']}; esperando VCP posterior",checks)
  return 'Orden FCI pendiente de VCP de fecha posterior; no significa compra ejecutada'
 return 'No hay fondo apto dentro de los límites de diversificación y liquidez'


def consider_nav_redemption(db,pid,now,funds,logs):
 """Defensive redemption review. NAV drawdown is NOT a guaranteed stop-loss."""
 if now.astimezone(TZ).weekday()>=5:return None
 port=db.get('atlas_portfolios',code='eq.'+CODE)[0]
 if not (port['autonomy_enabled'] and port['trading_enabled']):return None
 if db.get('atlas_orders',portfolio_id='eq.'+pid,status='eq.PENDING'):return None
 positions=db.get('atlas_positions',portfolio_id='eq.'+pid)
 for pos in positions:
  if pos['profile']!='conservador' or as_float(pos['quantity'])<=0:continue
  ins=db.get('atlas_instruments',id='eq.'+pos['instrument_id'])[0]
  if ins['asset_type']!='fondo':continue
  data=funds.get(ins['symbol'])
  if not data:continue
  f=data['info'];cost=as_float(pos['average_cost']);nav=f['nav']
  if cost<=0:continue
  nav_decline=nav/cost-1
  if nav_decline > -0.005 and (f['r30'] is None or f['r30']>=0):continue
  # This is a later-NAV redemption intent, not a same-day liquidation.
  rationale=(f"Revisión defensiva de FCI: variación vs costo {nav_decline:.2%}; r30 {f['r30']}. "
             "Rescate simulado al siguiente VCP, sin garantía de precio ni plazo.")
  dec=db.insert('atlas_decisions',{'portfolio_id':pid,'instrument_id':ins['id'],'profile':'conservador',
   'action':'vender','rationale':rationale,'risk_result':'aprobado',
   'risk_checks':{'trigger':'FCI_NAV_LOSS_OR_NEGATIVE_30D','later_nav_required':True}})[0]
  order_obj={'portfolio_id':pid,'decision_id':dec['id'],'instrument_id':ins['id'],
   'profile':'conservador','side':'SELL','quantity':pos['quantity'],
   'limit_price':round(nav*.97,6),'expires_at':(now+dt.timedelta(days=8)).isoformat(),
   'client_order_key':f'{now.astimezone(TZ).date()}-{ins["id"]}-SELL-conservador-NAV'}
  try:order=db.insert('atlas_orders',order_obj)[0]
  except Exception as ex:
   if 'duplicate' in str(ex).lower():return 'Rescate FCI ya evaluado hoy'
   raise
  try:db.insert('atlas_nav_intents',{'order_id':order['id'],'baseline_date':str(f['date']),
       'baseline_price':nav,'fund_name':f['name']})
  except Exception:
   db.patch('atlas_orders',{'id':'eq.'+order['id'],'status':'eq.PENDING'},
            {'status':'REJECTED','rejection_reason':'Fallo al guardar intención NAV'})
   raise
  record_event(db,pid,'FCI_PENDING_REDEMPTION',rationale,{'order_id':order['id']})
  return 'Rescate defensivo de FCI pendiente de VCP posterior'
 return None


def portfolio_valuation(db,pid,now,quotes,funds,mep,logs):
 port=db.get('atlas_portfolios',code='eq.'+CODE)[0]
 cash=as_float(port['cash_ars']);holdings=0;unpriced=[]
 for x in db.get('atlas_positions',portfolio_id='eq.'+pid):
  qty=as_float(x['quantity'])
  if qty<=0:continue
  ins=db.get('atlas_instruments',id='eq.'+x['instrument_id'])[0]
  if ins['asset_type']=='fondo':
   f=funds.get(ins['symbol']);mark=f['info']['nav'] if f else None
  else:
   q=quotes.get(ins['symbol']);mark=q[-1][1] if q else None
   if q and session_open(now) and (now-q[-1][0]).total_seconds()>3600:mark=None
  if mark is None:
   unpriced.append(ins['symbol']);continue
  holdings+=qty*mark
 # Do NOT present missing valuations as accurate portfolio equity.
 equity=round(cash+holdings,4) if not unpriced else None
 rate=mep.get('rate');usd=round(equity/rate,4) if rate and equity is not None else None
 try:
  db.insert('atlas_equity_history',{'portfolio_id':pid,'observed_at':now.isoformat(),
   'cash_ars':cash,'holdings_ars':round(holdings,4),'equity_ars':round(cash+holdings,4),
   'mep_ars':rate,'equity_usd':usd,'mep_source':mep.get('source'),
   'valuation_flags':{'incomplete':bool(unpriced),'unpriced_assets':unpriced}})
 except Exception as exc:logs.append({'equity_history_error':str(exc)[:120]})
 history=db.get('atlas_equity_history',portfolio_id='eq.'+pid,order='observed_at.desc',limit='150')
 history=list(reversed(history))
 return {'equity_ars':equity,'equity_usd':usd,'mep':mep,'unpriced':unpriced,'history':[
  {'at':x['observed_at'],'ars':None if (x.get('valuation_flags') or {}).get('incomplete') else as_float(x['equity_ars']),
  'usd':None if (x.get('valuation_flags') or {}).get('incomplete') or x.get('equity_usd') is None else as_float(x.get('equity_usd')),
  'mep':as_float(x.get('mep_ars')) or None} for x in history]}


def run():
 db=DB();now=dt.datetime.now(UTC);local=now.astimezone(TZ)
 # A missing SQL migration is fatal, not an invisible SUCCESS with zero operations.
 try:db.get('atlas_nav_intents',limit='1');db.get('atlas_equity_history',limit='1')
 except Exception as ex:raise RuntimeError('Falta aplicar sql/03_motor_fci_y_estadisticas.sql en Supabase: '+str(ex)[:250]) from ex
 port=db.get('atlas_portfolios',code='eq.'+CODE)[0];pid=port['id']
 db.insert('atlas_job_runs',{'job_name':'atlas_cloud_cycle','status':'RUNNING','details':{'at':iso_now()}})
 # Los datos de situación se exportan incluso si el mercado está cerrado.
 logs=[];quotes={};analyses=[]
 market_open=session_open(now)
 # Exclusión temporal defensiva de acontecimientos extraordinarios conocidos.
 if local.date().isoformat() in KNOWN_BYMA_CLOSED:market_open=False
 for symbol,(name,typ,profile,vol_limit) in UNIVERSE.items():
  try:
   points=fetch_chart(symbol,'1d','6mo');metrics=analysis(points)
   db.upsert('atlas_instruments',[{'symbol':symbol,'exchange':'XBUE','currency':'ARS','name':name,'asset_type':typ,'enabled':True}],'symbol,exchange,currency')
   ins=db.get('atlas_instruments',symbol='eq.'+symbol,exchange='eq.XBUE')[0]
   rationale=f"Técnico (sin fundamental/político): score {metrics['score']}; RSI {metrics['rsi']}; vol {metrics['vol']:.1%}; cierre fuente {metrics['date']}."
   db.insert('atlas_analyses',{'instrument_id':ins['id'],'profile':profile,'specialist':'TECNICO_REGLAS','thesis':rationale,'opinion':'esperar','confidence':min(100,metrics['score']),'evidence':[metrics],'limitations':'Sin comité de LLM ni fundamentales. Cotización Yahoo no certifica ejecución.','model_version':'paper_cloud_1'})
   analyses.append({'symbol':symbol,'profile':profile,'metrics':metrics,'source':'Yahoo Finance'})
  except Exception as ex:logs.append({'symbol':symbol,'error':'Histórico: '+str(ex)[:110]})
  try:quotes[symbol]=fetch_chart(symbol,'1m','1d')
  except Exception as ex:logs.append({'symbol':symbol,'error':'Intradiario: '+str(ex)[:110]})
 funds,local_fci_open=store_nav_observations(db,now,market_open,logs)
 if port['autonomy_enabled'] and port['trading_enabled']:
  fill_pending_nav(db,pid,now,funds,logs)
 # Noticias: en todos los ciclos, también con el mercado argentino cerrado.
 news_count=0
 try:
  items,news_errors=news_feed(now)
  for n in items:
   try:
    db.upsert('atlas_news',[n],'article_url');news_count+=1
   except Exception as ex:
    logs.append({'news_save_error':str(ex)[:110]})
  for err in news_errors:logs.append({'news_fetch_error':err})
 except Exception as ex:logs.append({'news_error':str(ex)[:120]})
 # El catálogo amplio es investigativo. Nada de estos activos se vuelve operable automáticamente.
 catalog_status=[]
 broad_catalog=local_watch_catalog()
 try:
  additions,catalog_status=dynamic_catalog()
  broad_catalog.extend(additions)
 except Exception as exc:
  catalog_status=[{'source':'catalogo','status':'ERROR','message':str(exc)[:180]}]
 # Índice único por tipo+símbolo para el buscador; no inventamos cotizaciones.
 unique_catalog={}
 for item in broad_catalog:
  unique_catalog[(item['category'],item['symbol'])]=item
 broad_catalog=list(unique_catalog.values())
 # Análisis de seguimiento adicional: no interviene en las órdenes.
 observed=[]
 for symbol,(name,exchange,currency,sector) in WATCH_ONLY.items():
  try:
   m=analysis(fetch_chart(symbol,'1d','6mo'))
   observed.append({'symbol':symbol,'name':name,'market':exchange,'currency':currency,'sector':sector,'metrics':m,'trade_allowed':False})
  except Exception as ex:logs.append({'watch_symbol':symbol,'error':str(ex)[:100]})

 committee=[decision_committee(a['symbol'],a['profile'],a['metrics'],news_count=news_count) for a in analyses]
 # Guardar disenso entre especialidades sin atribuirlo a agentes de IA inexistentes.
 for c in committee:
  try:
   ins=db.get('atlas_instruments',symbol='eq.'+c['symbol'],exchange='eq.XBUE')
   if ins:db.insert('atlas_analyses',{'instrument_id':ins[0]['id'],'profile':c['profile'],
    'specialist':'COMITE_EXPLICABLE_V2','thesis':f"Técnico: {c['technical']['view']}. Fundamental: {c['fundamental']['view']}. Macropolítica: {c['macro_politics']['view']}. Riesgo: {c['risk']['view']}.",
    'opinion':'esperar','confidence':None,'evidence':[c],
    'limitations':c['limitation'],'model_version':'atlas_explainable_2'})
  except Exception as exc:logs.append({'committee':c['symbol'],'error':str(exc)[:100]})
 if market_open:
  fill_pending(db,pid,now,quotes)
  port=db.get('atlas_portfolios',code='eq.'+CODE)[0]
  if port['autonomy_enabled'] and port['trading_enabled']:
   positions=position_map(db,pid)
   allocs={x['profile']:as_float(x['target_pct'])/100 for x in db.get('atlas_allocations',portfolio_id='eq.'+pid)}
   instruments={x['symbol']:x for x in db.get('atlas_instruments',exchange='eq.XBUE')}
   pending=db.get('atlas_orders',portfolio_id='eq.'+pid,status='eq.PENDING')
   if not pending:
    # Primero salidas por pérdidas y ganancias; no supone ganancia por vender.
    for a in analyses:
     sym=a['symbol'];ins=instruments.get(sym);pos=positions.get((ins['id'],a['profile'])) if ins else None
     if not pos or as_float(pos['quantity'])<=0:continue
     ok,why=valid_intraday_quote(quotes.get(sym),now)
     if not ok:continue
     allowed,_=instrument_session_allowed(sym,now)
     if not allowed:continue
     price=quotes[sym][-1][1];cost=as_float(pos['average_cost'])
     if cost<=0:continue
     change=price/cost-1
     stop=-0.08 if a['profile']=='moderado' else -0.12
     if change<=stop or a['metrics']['score']<=25:
      create_order(db,pid,ins,a['profile'],'SELL',int(as_float(pos['quantity'])),price*(1-SLIPPAGE-0.01),f'Salida defensiva: {change:.2%} vs costo, score {a["metrics"]["score"]}',a['metrics'],now)
      break
     take_review=0.20 if a['profile']=='moderado' else 0.30
     if change>=take_review and a['metrics']['score']<65:
      partial=max(1,int(as_float(pos['quantity'])/2))
      create_order(db,pid,ins,a['profile'],'SELL',partial,price*(1-SLIPPAGE-0.01),
       f'Reducción parcial por ganancia {change:.2%} y deterioro técnico score {a["metrics"]["score"]}; no venta automática por ganancia sola',a['metrics'],now)
      break
    else:
     # Solamente compras; el 60% conservador queda en efectivo, y nunca se usa USD sin MEP.
     for a in sorted(analyses,key=lambda x:x['metrics']['score'],reverse=True):
      sym=a['symbol'];p=a['profile'];ins=instruments.get(sym)
      if not ins:continue
      q=quotes.get(sym);ok,why=valid_intraday_quote(q,now)
      if not ok:continue
      allowed,_=instrument_session_allowed(sym,now)
      if not allowed:continue
      score=a['metrics']['score'];rsi=a['metrics']['rsi'];vol=a['metrics']['vol']
      if score<BUY_SCORE or not 38<=rsi<=66 or vol>UNIVERSE[sym][3]:continue
      if (ins['id'],p) in positions and as_float(positions[(ins['id'],p)]['quantity'])>0:continue
      price=q[-1][1];budget=as_float(port['initial_cash'])*allocs.get(p,0)
      already=sum(as_float(v['quantity'])*as_float(v['average_cost']) for (iid,pf),v in positions.items() if pf==p)
      budget=min(budget,MAX_ORDER_BY_PROFILE[p],as_float(port['initial_cash'])*MAX_PER_EMITTER,as_float(port['cash_ars']),max(0,budget-already))
      qty=int(budget/(price*(1+FEE+SLIPPAGE+0.01)))
      if qty<=0:continue
      create_order(db,pid,ins,p,'BUY',qty,price*(1+SLIPPAGE+0.01),f'Entrada técnica score {score}, RSI {rsi}, vol {vol:.2%}. Pendiente de precio posterior.',a['metrics'],now)
      break
 else:
  logs.append({'session':'Sin rueda o fuera de sesión: sin órdenes nuevas ni fills'})
 conservative_status=consider_nav_redemption(db,pid,now,funds,logs)
 if not conservative_status:
  conservative_status=consider_nav_subscription(db,pid,now,funds,local_fci_open,logs)
 record_event(db,pid,'CONSERVATIVE_REVIEW',conservative_status,{'candidate_funds':len(funds)})
 for item in logs[:12]:
  try:record_event(db,pid,'DATA_WARNING',json.dumps(item,ensure_ascii=False))
  except Exception:pass
 mep=mep_quote(now)
 valuation=portfolio_valuation(db,pid,now,quotes,funds,mep,logs)
 export_snapshot(db,now,market_open,logs,analyses,quotes,observed,news_count,broad_catalog,catalog_status,committee,valuation,conservative_status,funds)
 jobs=db.get('atlas_job_runs',job_name='eq.atlas_cloud_cycle',order='id.desc',limit='1')
 if jobs:db.patch('atlas_job_runs',{'id':'eq.'+str(jobs[0]['id'])},{'finished_at':iso_now(),'status':'SUCCESS','details':{'market_open':market_open,'warnings':len(logs),'conservative':conservative_status[:100],'news_refreshed':news_count,'watch_count':len(observed),'catalog_count':len(broad_catalog)}})
 print(json.dumps({'byma_open':market_open,'local_tradable_analyses':len(analyses),'global_watch_analyses':len(observed),'news_refreshed':news_count,'catalog_count':len(broad_catalog),'warnings':len(logs),'conservative_status':conservative_status[:180]},ensure_ascii=False))


def export_snapshot(db,now,market_open,logs,analyses,quotes,observed,news_count,broad_catalog,catalog_status,committee,valuation,conservative_status,funds):
 p=db.get('atlas_portfolios',code='eq.'+CODE)[0];pid=p['id']
 positions=db.get('atlas_positions',portfolio_id='eq.'+pid)
 instruments=db.get('atlas_instruments')
 symbol_by_id={x['id']:x['symbol'] for x in instruments}
 out=[]
 for pos in positions:
  if as_float(pos['quantity'])<=0:continue
  symbol=symbol_by_id.get(pos['instrument_id'],'?');q=quotes.get(symbol)
  is_fci=symbol in funds
  mark=funds[symbol]['info']['nav'] if is_fci else (q[-1][1] if q else None)
  out.append({'symbol':symbol,'profile':pos['profile'],'quantity':as_float(pos['quantity']),'average_cost':as_float(pos['average_cost']),'mark':mark,'currency':'ARS','realized_pnl':as_float(pos['realized_pnl'])})
 orders=db.get('atlas_orders',portfolio_id='eq.'+pid,order='placed_at.desc',limit='30')
 audit=db.get('atlas_audit_events',portfolio_id='eq.'+pid,order='occurred_at.desc',limit='40')
 news=db.get('atlas_news',order='published_at.desc',limit='300')
 allocations=db.get('atlas_allocations',portfolio_id='eq.'+pid)
 last_decisions=db.get('atlas_decisions',portfolio_id='eq.'+pid,order='decided_at.desc',limit='30')
 snapshot={'valuation':valuation,'conservative_status':conservative_status,'as_of':iso_now(),'market_open':market_open,'market_detail':{'XBUE':{'open':market_open,'local_time':now.astimezone(TZ).isoformat(),'reason':('Feriado confirmado en BYMA' if now.astimezone(TZ).date().isoformat() in KNOWN_BYMA_CLOSED else '11/11: rueda excepcional; CEDEAR T+1 no simulado, órdenes CEDEAR bloqueadas' if now.astimezone(TZ).date().isoformat() in SPECIAL_CEDEAR_T1_ONLY else 'Calendario local exchange_calendars; restricciones extraordinarias NO garantizadas'),'source':'exchange_calendars + excepciones fechadas'},'US':{'open':None,'reason':'Seguimiento de precios únicamente; no se verifica sesión para negociación automática'}},'news_fetched_this_cycle':news_count,'cycle_kind':('PREAPERTURA' if now.astimezone(TZ).time().hour<10 else 'CIERRE' if now.astimezone(TZ).time().hour>=18 else 'MONITOREO'), 'execution_policy':'FCI solo se simula con cuotaparte de fecha posterior; instrumentos bursátiles necesitan precio posterior. No se completa una orden sin precio intradiario posterior; CEDEAR 11/11 T+1 bloqueado si no se modela liquidación','instrument_catalog':broad_catalog,'catalog_status':catalog_status,'committee':committee,'watchlist':observed,'feed':'Yahoo Finance (no oficial; datos potencialmente demorados)','cash_ars':as_float(p['cash_ars']),'cash_usd':as_float(p['cash_usd']),'initial_ars':as_float(p['initial_cash']),'autonomy_enabled':p['autonomy_enabled'],'trading_enabled':p['trading_enabled'],'allocations':[{ 'profile':x['profile'],'target_pct':as_float(x['target_pct'])} for x in allocations],'positions':out,'orders':[{'status':x['status'],'side':x['side'],'quantity':as_float(x['quantity']),'limit_price':as_float(x['limit_price']),'placed_at':x['placed_at'],'symbol':symbol_by_id.get(x['instrument_id'],'?')} for x in orders],'decisions':[{'action':x['action'],'rationale':x['rationale'],'decided_at':x['decided_at'],'symbol':symbol_by_id.get(x['instrument_id'],'?')} for x in last_decisions],'audit':[{'type':x['event_type'],'message':x['message'],'at':x['occurred_at']} for x in audit],'news':[{'title':x['title'],'url':x['article_url'],'publisher':x['publisher'],'country':x['country'],'sector':x['sector'],'published_at':x.get('published_at')} for x in news],'analyses':analyses,'warnings':logs,'note':'Cartera ficticia; informe públicamente visible si GitHub Pages es público. Los fills son estimaciones, no transacciones reales.'}
 target=ROOT/'docs'/'snapshot.json';target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':run()
