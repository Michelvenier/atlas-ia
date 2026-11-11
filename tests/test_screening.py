from app.screening import screen_one, screen_catalog

def test_missing_quote():
    x=screen_one({'symbol':'X','category':'accion','price':None,'stale':True})
    assert not x['trade_eligible'] and 'SIN_COTIZACION' in x['reasons']

def test_fci():
    x=screen_one({'symbol':'FCI1','category':'fci','price':100.0,'yield_pct':8.0,'stale':False,'source':'fuente'})
    assert x['evidence_ready'] and not x['trade_eligible']

def test_1000():
    data=[{'symbol':f'F{i}', 'category':'fci', 'price':100,'yield_pct':4,'stale':False,'source':'fuente'} for i in range(1100)]
    r=screen_catalog(data)
    assert r['catalog_screened']==1100 and r['with_minimum_documentary_data']==1100
