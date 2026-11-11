"""Evaluación preliminar por tipo: NO confundir con análisis técnico ni habilitación de compra."""
import math
from collections import Counter

def number(x):
    try:
        n=float(x)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):return None

def screen_one(item):
    kind=str(item.get('category') or 'desconocido').lower()
    p=number(item.get('price'))
    y=number(item.get('yield_pct'))
    dur=number(item.get('duration'))
    stale=item.get('stale') is True
    source=str(item.get('source') or '')
    reasons=[]
    if kind in ('bono','letra','on','deuda'):
        if p is None or p<=0:reasons.append('SIN_PRECIO')
        if y is None:reasons.append('SIN_TIR')
        if dur is None:reasons.append('SIN_DURATION')
        if not item.get('maturity'):reasons.append('SIN_VENCIMIENTO')
        if stale:reasons.append('PRECIO_DESACTUALIZADO')
        if y is not None and not (-100<y<500):reasons.append('TIR_ANOMALA')
    elif kind=='fci':
        if p is None or p<=0:reasons.append('SIN_CUOTAPARTE')
        if y is None:reasons.append('SIN_RENDIMIENTO_PUBLICADO')
        if stale:reasons.append('CUOTAPARTE_INCIERTA')
    else:
        if p is None or p<=0:reasons.append('SIN_COTIZACION')
        if stale:reasons.append('SIN_FRESCURA_VERIFICADA')
    if not source:reasons.append('SIN_FUENTE')
    ready=not reasons and kind in ('bono','letra','on','fci')
    # 'ready' significa datos mínimos disponibles, no aptitud para negociar.
    return {'symbol':str(item.get('symbol') or ''),'category':kind,'evidence_ready':ready,
            'screening':'DATOS_MINIMOS' if ready else 'DATOS_INSUFICIENTES',
            'reasons':reasons,'trade_eligible':False,
            'interpretation':'Preselección documental; NO es análisis fundamental completo ni orden de compra'}

def screen_catalog(items):
    records=[screen_one(x) for x in items if x.get('symbol')]
    cats=Counter(x['category'] for x in records)
    blocked=Counter(reason for x in records for reason in x['reasons'])
    return {'catalog_screened':len(records),'with_minimum_documentary_data':sum(x['evidence_ready'] for x in records),
            'by_category':dict(cats),'missing_data_reasons':dict(blocked),
            'note':'Evaluación documental preliminar, no análisis técnico ni fundamental; cotizaciones faltantes no se inventan',
            'examples':records[:25]}
