"""ATLAS IA: motor de paper trading, sin cuentas de broker.
Publica snapshot público SOLO con información ficticia.
La compra usa un precio posterior a una orden, no el último precio al generarla.
Yahoo chart es fuente gratuita NO certificada; ejecuciones son estimaciones.
"""
import os, json, time, math, statistics, datetime as dt, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
import pandas as pd
import exchange_calendars as xc

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
MAX_ORDER_BY_PROFILE={'moderado':300000,'agresivo':200000}


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
 try:
  cal=xc.get_calendar('XBUE')
  return bool(cal.is_open_on_minute(pd.Timestamp(now).floor('min')))
 except Exception:return False

def valid_intraday_quote(q,now):
 if not q:return False,'SIN_PRECIO'
 t,p=q[-1]
 age=(now-t).total_seconds()
 if not (0<=age<=QUOTE_MAX_AGE_S):return False,'PRECIO_ANTIGUO'
 try:
  cal=xc.get_calendar('XBUE')
  if not cal.is_open_on_minute(pd.Timestamp(t).floor('min')):return False,'COTIZACION_FUERA_DE_RUEDA'
 except Exception:return False,'CALENDARIO_NO_DISPONIBLE'
 return True,'VALIDO_CON_DEMORA_POTENCIAL'


def news_feed():
 url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':'economía Argentina petróleo política mercados bolsa cuando:1d','hl':'es-419','gl':'AR','ceid':'AR:es-419'})
 r=requests.get(url,timeout=15,headers={'User-Agent':'Mozilla/5.0'});r.raise_for_status()
 root=ET.fromstring(r.content)
 out=[]
 for n in root.findall('.//item')[:12]:
  link=n.findtext('link') or ''
  if not link.startswith('https://'):continue
  out.append({'title':(n.findtext('title') or '')[:500],'article_url':link,'publisher':n.findtext('source') or 'Google News','summary':'Titular de agregador; no se usó para determinar compras','country':'Argentina','sector':'economía','metadata':{'source':'Google News RSS'}})
 return out


def position_map(db,pid):
 positions=db.get('atlas_positions',portfolio_id='eq.'+pid)
 return {(x['instrument_id'],x['profile']):x for x in positions}


def record_event(db,pid,kind,msg,payload=None):
 db.insert('atlas_audit_events',{'portfolio_id':pid,'event_type':kind,'message':msg[:800],'payload':payload or {}})


def fill_pending(db,pid,now,latest):
 orders=db.get('atlas_orders',portfolio_id='eq.'+pid,status='eq.PENDING')
 for order in orders:
  try:
   ins=db.get('atlas_instruments',id='eq.'+order['instrument_id'])[0]
   sym=ins['symbol'];q=latest.get(sym)
   if not session_open(now):continue
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


def run():
 db=DB();now=dt.datetime.now(UTC);local=now.astimezone(TZ)
 port=db.get('atlas_portfolios',code='eq.'+CODE)[0];pid=port['id']
 db.insert('atlas_job_runs',{'job_name':'atlas_cloud_cycle','status':'RUNNING','details':{'at':iso_now()}})
 # Los datos de situación se exportan incluso si el mercado está cerrado.
 logs=[];quotes={};analyses=[]
 market_open=session_open(now)
 # Exclusión temporal defensiva de acontecimientos extraordinarios conocidos.
 known_closed={'2026-11-09','2026-11-10'}
 if local.date().isoformat() in known_closed:market_open=False
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
 if local.hour in (8,10,19):
  try:
   for n in news_feed():
    try:db.upsert('atlas_news',[n],'article_url')
    except Exception:pass
  except Exception as ex:logs.append({'news_error':str(ex)[:100]})
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
     price=quotes[sym][-1][1];cost=as_float(pos['average_cost'])
     if cost<=0:continue
     change=price/cost-1
     stop=-0.08 if a['profile']=='moderado' else -0.12
     if change<=stop or a['metrics']['score']<=25:
      create_order(db,pid,ins,a['profile'],'SELL',int(as_float(pos['quantity'])),price*(1-SLIPPAGE-0.01),f'Salida defensiva: {change:.2%} vs costo, score {a["metrics"]["score"]}',a['metrics'],now)
      break
    else:
     # Solamente compras; el 60% conservador queda en efectivo, y nunca se usa USD sin MEP.
     for a in sorted(analyses,key=lambda x:x['metrics']['score'],reverse=True):
      sym=a['symbol'];p=a['profile'];ins=instruments.get(sym)
      if not ins:continue
      q=quotes.get(sym);ok,why=valid_intraday_quote(q,now)
      if not ok:continue
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
 for item in logs[:12]:
  try:record_event(db,pid,'DATA_WARNING',json.dumps(item,ensure_ascii=False))
  except Exception:pass
 export_snapshot(db,now,market_open,logs,analyses,quotes)
 jobs=db.get('atlas_job_runs',job_name='eq.atlas_cloud_cycle',order='id.desc',limit='1')
 if jobs:db.patch('atlas_job_runs',{'id':'eq.'+str(jobs[0]['id'])},{'finished_at':iso_now(),'status':'SUCCESS','details':{'market_open':market_open,'warnings':len(logs)}})
 print(json.dumps({'market_open':market_open,'analyses':len(analyses),'warnings':len(logs)},ensure_ascii=False))


def export_snapshot(db,now,market_open,logs,analyses,quotes):
 p=db.get('atlas_portfolios',code='eq.'+CODE)[0];pid=p['id']
 positions=db.get('atlas_positions',portfolio_id='eq.'+pid)
 instruments=db.get('atlas_instruments')
 symbol_by_id={x['id']:x['symbol'] for x in instruments}
 out=[]
 for pos in positions:
  if as_float(pos['quantity'])<=0:continue
  symbol=symbol_by_id.get(pos['instrument_id'],'?');q=quotes.get(symbol)
  out.append({'symbol':symbol,'profile':pos['profile'],'quantity':as_float(pos['quantity']),'average_cost':as_float(pos['average_cost']),'mark':q[-1][1] if q else None,'currency':'ARS','realized_pnl':as_float(pos['realized_pnl'])})
 orders=db.get('atlas_orders',portfolio_id='eq.'+pid,order='placed_at.desc',limit='30')
 audit=db.get('atlas_audit_events',portfolio_id='eq.'+pid,order='occurred_at.desc',limit='40')
 news=db.get('atlas_news',order='published_at.desc',limit='30')
 allocations=db.get('atlas_allocations',portfolio_id='eq.'+pid)
 last_decisions=db.get('atlas_decisions',portfolio_id='eq.'+pid,order='decided_at.desc',limit='30')
 snapshot={'as_of':iso_now(),'market_open':market_open,'feed':'Yahoo Finance (no oficial; datos potencialmente demorados)','cash_ars':as_float(p['cash_ars']),'cash_usd':as_float(p['cash_usd']),'initial_ars':as_float(p['initial_cash']),'autonomy_enabled':p['autonomy_enabled'],'trading_enabled':p['trading_enabled'],'allocations':[{ 'profile':x['profile'],'target_pct':as_float(x['target_pct'])} for x in allocations],'positions':out,'orders':[{'status':x['status'],'side':x['side'],'quantity':as_float(x['quantity']),'limit_price':as_float(x['limit_price']),'placed_at':x['placed_at'],'symbol':symbol_by_id.get(x['instrument_id'],'?')} for x in orders],'decisions':[{'action':x['action'],'rationale':x['rationale'],'decided_at':x['decided_at'],'symbol':symbol_by_id.get(x['instrument_id'],'?')} for x in last_decisions],'audit':[{'type':x['event_type'],'message':x['message'],'at':x['occurred_at']} for x in audit],'news':[{'title':x['title'],'url':x['article_url'],'publisher':x['publisher'],'country':x['country'],'sector':x['sector']} for x in news],'analyses':analyses,'warnings':logs,'note':'Cartera ficticia; informe públicamente visible si GitHub Pages es público. Los fills son estimaciones, no transacciones reales.'}
 target=ROOT/'docs'/'snapshot.json';target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':run()
