import datetime as dt
from zoneinfo import ZoneInfo
from app.scanner import active_symbol_batch,batch_summary

def test_cyclic_scanning_preserves_core():
    universe={str(i):(str(i),'accion','moderado',.4) for i in range(85)}
    now=dt.datetime(2026,11,11,13,0,tzinfo=ZoneInfo('America/Argentina/Buenos_Aires'))
    selected=active_symbol_batch(universe,now,12,14)
    assert len(selected)==26
    assert all(str(i) in selected for i in range(12))
    next_slot=active_symbol_batch(universe,now+dt.timedelta(minutes=15),12,14)
    assert selected!=next_slot

def test_scanner_counts_are_not_catalog_counts():
    d=batch_summary({str(i):i for i in range(100)},{str(i):i for i in range(20)},[1]*15,dt.datetime.now(dt.timezone.utc))
    assert d['technical_universe_size']==100
    assert d['technical_batch_success']==15
    assert d['technical_batch_failed']==5
