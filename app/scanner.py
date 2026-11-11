"""Escaneo escalonado de símbolos argentinos/CEDEAR con rotación determinista.
No convierte catálogo documental en 1.000 análisis técnicos: informa la cobertura real.
"""
import datetime as dt
from zoneinfo import ZoneInfo
VERSION='ATLAS-INTEGRAL-2026.11-consolidado'
LOCAL=ZoneInfo('America/Argentina/Buenos_Aires')

def active_symbol_batch(universe,now,core_count=12,extra_count=14):
    keys=list(universe)
    core=keys[:core_count]
    other=keys[core_count:]
    if not other:return {k:universe[k] for k in keys}
    local=now.astimezone(LOCAL)
    # Las tandas se desplazan cada 15 minutos, incluso en ejecuciones manuales.
    slot=((local.toordinal()*96)+(local.hour*4)+(local.minute//15))
    start=(slot*extra_count)%len(other)
    sample=[other[(start+j)%len(other)] for j in range(min(extra_count,len(other)))]
    return {k:universe[k] for k in core+sample}

def batch_summary(universe,batch,analyses,now):
    return {'technical_universe_size':len(universe),
      'technical_batch_candidates':len(batch),
      'technical_batch_success':len(analyses),
      'technical_batch_failed':max(0,len(batch)-len(analyses)),
      'batch_at':now.isoformat(),
      'coverage_note':'Escaneo histórico por tandas. Documental, técnico y operable son conjuntos distintos.'}
