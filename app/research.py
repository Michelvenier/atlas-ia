"""Catálogo documental y comité explicable. Nunca cursa órdenes ni supone que NAV=TICK negociable."""
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor
import requests

SOURCE='https://compararfondos.com.ar/api'
HEADERS={'User-Agent':'ATLAS-IA-educational-research/2.0'}
# Catálogo de seguimiento: identificación preliminar, no listado certificado.
WATCH={
 'accion': ['YPFD.BA','GGAL.BA','PAMP.BA','BMA.BA','BBAR.BA','SUPV.BA','CEPU.BA','EDN.BA','TGSU2.BA','TRAN.BA','ALUA.BA','TXAR.BA','COME.BA','BYMA.BA','LOMA.BA','MIRG.BA','CRES.BA','IRSA.BA','METR.BA','VALO.BA'],
 'cedear': ['AAPL.BA','MSFT.BA','SPY.BA','QQQ.BA','NVDA.BA','AMZN.BA','GOOGL.BA','META.BA','TSLA.BA','XOM.BA','KO.BA','JPM.BA','BRKB.BA','MELI.BA','GLD.BA','DIA.BA','V.BA','WMT.BA','DISN.BA','BABA.BA','XLE.BA','PFE.BA','UNH.BA'],
 'etf': ['SPY','QQQ','VTI','VOO','VT','TLT','SHY','BIL','GLD','XLE','XLF','XLK','EEM'],
 'accion_ext': ['AAPL','MSFT','NVDA','AMZN','GOOGL','META','TSLA','XOM','CVX','JPM','MELI','KO','WMT','BRK-B']}


def safe_number(v):
 try:
  f=float(v)
  return round(f,5) if f==f and abs(f)<1e15 else None
 except (TypeError,ValueError,OverflowError):return None


def get_json(path):
 r=requests.get(SOURCE+'/'+path,headers=HEADERS,timeout=16)
 r.raise_for_status()
 data=r.json()
 if not isinstance(data,dict):raise ValueError('El proveedor no devolvió un objeto')
 return data


def dynamic_catalog():
 """No convierte precios ajenos en 'cotizaciones ejecutables'."""
 rows=[];statuses=[]
 with ThreadPoolExecutor(max_workers=2) as ex:
  fs={ex.submit(get_json,route):typ for route,typ in [('bonos','deuda'),('fondos','fci')]}
  for fut,typ in fs.items():
   try:
    doc=fut.result()
    dataset=doc.get('bonds' if typ=='deuda' else 'funds',[])
    if not isinstance(dataset,list):raise ValueError('Listado no disponible')
    for x in dataset[:650]:
     if not isinstance(x,dict):continue
     if typ=='deuda':
      kind=str(x.get('tipo') or 'bono')
      cat='on' if kind.upper()=='ON' else 'letra' if kind.upper() in ('LECAP','BONCAP') else 'bono'
      sym=str(x.get('ticker') or '').strip()
      if not sym:continue
      rows.append({'symbol':sym,'name':str(x.get('nombre') or sym),'category':cat,'country':'Argentina',
       'currency':x.get('moneda'),'price':safe_number(x.get('precio')),'yield_pct':safe_number(x.get('tir')),
       'duration':safe_number(x.get('duration')),'maturity':x.get('vencimiento'),'stale':bool(x.get('precioStale',True)),
       'source':'compararfondos.com.ar vía /api/bonos','data_kind':'referencia_demorada','trade_eligible':False,
       'notes':kind+' · consultar prospecto, especie, precio y volumen antes de simular'})
     else:
      sym=str(x.get('codigoCafci') or x.get('nombre') or '').strip()
      if not sym:continue
      rows.append({'symbol':sym,'name':str(x.get('nombre') or sym),'category':'fci','country':'Argentina',
       'currency':x.get('moneda'),'price':safe_number(x.get('vcpHoy')),'yield_pct':safe_number(x.get('r30')),
       'duration':None,'maturity':None,'stale':bool(x.get('saltoPendiente')),
       'source':'compararfondos.com.ar vía /api/fondos','data_kind':'valor_cuotaparte_diario','trade_eligible':False,
       'notes':str(x.get('tipo') or '')+' · VCP NO es precio intradiario ejecutable; verificar rescate y corte'})
    statuses.append({'source':typ,'status':'OK','items':len(dataset),'age_min':doc.get('age_min'),'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat()})
   except Exception as exc:
    statuses.append({'source':typ,'status':'ERROR','message':str(exc)[:200]})
 return rows,statuses


def local_watch_catalog():
 rows=[]
 for typ,syms in WATCH.items():
  for sym in syms:
   rows.append({'symbol':sym,'name':sym,'category':'accion' if typ=='accion_ext' else typ,
    'country':'EE.UU.' if typ in ('accion_ext','etf') else 'Argentina',
    'currency':'USD' if typ in ('accion_ext','etf') else 'ARS','price':None,'yield_pct':None,'duration':None,
    'maturity':None,'stale':True,'source':'lista de símbolos candidatos; sin validación en este ciclo',
    'data_kind':'catalogo_no_verificado','trade_eligible':False,
    'notes':'Solo seguimiento; no se habilita operación sin identificación y datos de mercado'})
 return rows


def decision_committee(symbol,profile,metrics,fundamental=None,news_count=0):
 """Comité basado en reglas; no afirma disponer de agentes LLM ni balances que no leyó."""
 tech=int(metrics.get('score',0));rsi=metrics.get('rsi');vol=metrics.get('vol')
 fund_ok=isinstance(fundamental,dict) and fundamental.get('verified') is True
 risk='ADVERTENCIA' if vol is None or vol>0.35 else 'DENTRO_DE_LIMITE'
 tech_signal='FAVORABLE' if tech>=78 else 'NEUTRAL' if tech>=45 else 'DESFAVORABLE'
 fundamental_view='SIN_EVIDENCIA' if not fund_ok else fundamental.get('opinion','SIN_EVIDENCIA')
 macro_view='SIN_EVALUACION' # titulares NO son análisis macro/político validado
 outcome='OBSERVAR' if tech_signal=='FAVORABLE' else 'ESPERAR'
 return {'symbol':symbol,'profile':profile,'decision':outcome,'technical':{'view':tech_signal,'score':tech,'rsi':rsi,'volatility':vol},
  'fundamental':{'view':fundamental_view,'basis':'No se recibió balance/fuente estructurada verificada' if not fund_ok else fundamental.get('basis')},
  'macro_politics':{'view':macro_view,'basis':'No inferir tesis política únicamente desde titulares'},
  'risk':{'view':risk,'basis':'Volatilidad histórica; no reemplaza control independiente de ejecución'},
  'news_available':news_count,'trade_authorized_by_committee':False,
  'limitation':'Comité EXPLICABLE por reglas. Análisis fundamental y geopolítico completos requieren proveedores y modelos adicionales.'}
