"""Conservative simulated NAV-subscriptions; no broker, no asserted execution prices.
An order is created using an observed historical NAV and can be estimated only
at a *subsequently published different NAV date*. NAV values are not executable quotes.
"""
import datetime as dt
import math
from zoneinfo import ZoneInfo
from .research import get_json
TZ=ZoneInfo('America/Argentina/Buenos_Aires')
NAV_SOURCE='compararfondos.com.ar /api/fondos (VCP diario informativo)'


def nav_date(value):
    if not value:return None
    raw=str(value).strip()[:10]
    for fmt in ('%Y-%m-%d','%d/%m/%Y'):
        try:return dt.datetime.strptime(raw,fmt).date()
        except ValueError:pass
    return None


def finite(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):return None


def selected_funds(doc,now):
    """Limit to ARS money-market funds with apparently regular NAV series.
    Listing is only a candidate screen; it does not verify subscriber eligibility.
    """
    raw=doc.get('funds') or []
    result=[]
    if doc.get('status') not in (None,'ok','OK','success') or not isinstance(raw,list):return result
    for x in raw:
        if not isinstance(x,dict):continue
        currency=str(x.get('moneda') or '').upper().strip()
        typ=str(x.get('tipo') or '').upper().strip()
        name=str(x.get('nombre') or '').strip()
        code=str(x.get('codigoCafci') or name).strip()
        manager=str(x.get('gerente') or x.get('gestora') or '').strip()
        day=nav_date(x.get('fechaVcp'))
        price=finite(x.get('vcpHoy'))
        r30=finite(x.get('r30'))
        delta=finite(x.get('variacionDia'))
        if not name or not code or typ!='MM' or currency not in ('ARS','PESOS','$','PESO ARGENTINO'):
            continue
        if day is None or price is None or price<=0 or day>now.date() or (now.date()-day).days>5:
            continue
        if x.get('saltoPendiente') or (delta is not None and abs(delta)>2.0):continue
        buy_eligible=(r30 is not None and 0<=r30<=20 and bool(manager))
        result.append({'symbol':code[:120],'name':name[:255], 'date':day,'nav':price,
                       'r30':r30,'manager':manager,'buy_eligible':buy_eligible,'source':NAV_SOURCE,'kind':'suscripcion_cuotaparte'})
    # Pick different managers where possible; never decide from one return number alone.
    return sorted(result,key=lambda a:(-(a['r30'] or 0),a['symbol']))


def nav_quote_timestamp(day):
    # Stable date marker, NOT the actual NAV publication time (which is unknown).
    return dt.datetime.combine(day,dt.time(12),TZ).astimezone(dt.timezone.utc)


def conservative_window(now,market_open):
    local=now.astimezone(TZ)
    return market_open and dt.time(10,30)<=local.time().replace(tzinfo=None)<dt.time(15,0)
