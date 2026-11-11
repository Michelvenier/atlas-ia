"""Plazos fijos ficticios con TEA publicada en API oficial del BCRA.
No verifica elegibilidad real del usuario en un banco; no envía solicitudes.
"""
import datetime as dt
import math
import requests
from zoneinfo import ZoneInfo
TZ=ZoneInfo('America/Argentina/Buenos_Aires')
URL='https://api.bcra.gob.ar/transparencia/v1.0/PlazosFijos'
# Bancos relativamente establecidos para evitar perseguir una TEA atípica.
BANKS=('NACION','PROVINCIA DE BUENOS AIRES','GALICIA','SANTANDER','BBVA','MACRO','CREDICOOP','CIUDAD','PATAGONIA')

def bank_offer(doc, now, amount=200000):
    """Return published eligible 30d opportunity, or (None, explanatory reason).
    The selection never presumes actual bank onboarding or contractual eligibility.
    """
    if not isinstance(doc, dict) or not isinstance(doc.get('results'),list):return None,'Respuesta BCRA sin lista results'
    valid=[];reasons={}
    for row in doc['results']:
        if not isinstance(row,dict):continue
        name=str(row.get('descripcionEntidad') or '').upper()
        if not any(b in name for b in BANKS):continue
        date_raw=str(row.get('fechaInformacion') or '')[:10]
        try:date=dt.date.fromisoformat(date_raw)
        except ValueError:reasons['sin_fecha']=reasons.get('sin_fecha',0)+1;continue
        age=(now.astimezone(TZ).date()-date).days
        if not 0<=age<=3:reasons['desactualizada']=reasons.get('desactualizada',0)+1;continue
        try:
            tea=float(row.get('tasaEfectivaAnualMinima'))
            minimum=float(row.get('montoMinimoInvertir') or 0)
            days=float(row.get('plazoMinimoInvertirDias') or 0)
        except (TypeError,ValueError):continue
        if not all(math.isfinite(v) for v in (tea,minimum,days)):continue
        if not 1<=tea<=100 or minimum>amount or days>30:continue
        # En la simulación el plazo es 30d; el emisor puede imponer condiciones no observadas.
        valid.append({'bank':name,'tea':tea,'rate_date':date.isoformat(),
            'days':30,'min_amount':minimum,'product':str(row.get('denominacion') or '')[:180],
            'source':URL,'restrictions':str(row.get('condicionesCorto') or '')[:300]})
    if not valid:return None,'Sin ofertas de bancos seleccionados para $200.000/30 días con fecha y TEA verificables; '+str(reasons)
    valid.sort(key=lambda x:(-x['tea'],x['bank']))
    return valid[0],None

def fetch_offer(now,amount=200000):
    r=requests.get(URL,timeout=18,headers={'User-Agent':'ATLAS-IA-Paper/5.0','Accept':'application/json'})
    r.raise_for_status()
    return bank_offer(r.json(),now,amount)
