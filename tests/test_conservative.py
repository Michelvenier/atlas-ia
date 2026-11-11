import unittest,datetime as dt
from zoneinfo import ZoneInfo
from app.conservative import selected_funds,nav_date,conservative_window,nav_quote_timestamp
from app.engine import mep_quote
TZ=ZoneInfo('America/Argentina/Buenos_Aires')

class TestConservative(unittest.TestCase):
    def setUp(self):self.now=dt.datetime(2026,11,11,12,30,tzinfo=TZ)
    def test_filter_currency_and_money_market(self):
        doc={'status':'ok','funds':[
            {'nombre':'MM1','codigoCafci':'1','moneda':'ARS','gestora':'Gerente X','tipo':'MM','fechaVcp':'2026-11-11','vcpHoy':100,'r30':2},
            {'nombre':'USD-MM','moneda':'USD','tipo':'MM','fechaVcp':'2026-11-11','vcpHoy':100,'r30':2},
            {'nombre':'Renta variable','moneda':'ARS','tipo':'RV','fechaVcp':'2026-11-11','vcpHoy':100,'r30':2}]}
        out=selected_funds(doc,self.now)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['symbol'],'1')
        self.assertTrue(out[0]['buy_eligible'])
    def test_negative_return_can_be_valued_not_bought(self):
        doc={'funds':[{'nombre':'MM1','moneda':'ARS','gestora':'Gerente X','tipo':'MM','fechaVcp':'2026-11-11','vcpHoy':100,'r30':-1}]}
        out=selected_funds(doc,self.now)
        self.assertEqual(len(out),1)
        self.assertFalse(out[0]['buy_eligible'])
    def test_stale_and_split_block(self):
        doc={'funds':[{'nombre':'MM1','moneda':'ARS','gestora':'Gerente X','tipo':'MM','fechaVcp':'2026-10-01','vcpHoy':100,'r30':2},
         {'nombre':'MM2','moneda':'ARS','gestora':'Gerente X','tipo':'MM','fechaVcp':'2026-11-11','vcpHoy':200,'r30':2,'saltoPendiente':{'fecha':'2026-11-11'}}]}
        self.assertEqual(selected_funds(doc,self.now),[])
    def test_nav_is_date_marker_not_trade_time(self):
        self.assertEqual(nav_quote_timestamp(dt.date(2026,11,11)).astimezone(TZ).hour,12)
    def test_subscription_window(self):
        self.assertTrue(conservative_window(self.now,True))
        self.assertFalse(conservative_window(self.now,False))
        self.assertFalse(conservative_window(self.now.replace(hour=16),True))
    def test_bad_nav_date(self):self.assertIsNone(nav_date('not-a-date'))
if __name__=='__main__':unittest.main()

class FakeDB:
    def __init__(self):
        self.rows={'atlas_portfolios':[{'id':'pid','code':'ATLAS-DEMO-001','initial_cash':10000000,
                  'cash_ars':10000000,'autonomy_enabled':True,'trading_enabled':True}],
                   'atlas_allocations':[{'profile':'conservador','target_pct':60}],
                   'atlas_positions':[],'atlas_orders':[],'atlas_nav_intents':[],
                   'atlas_decisions':[],'atlas_audit_events':[]}
    def get(self,table,**params):
        res=self.rows.get(table,[])
        if table=='atlas_instruments':return []
        if table=='atlas_orders':return [x for x in res if x.get('status')=='PENDING']
        return res
    def insert(self,table,obj):
        x=dict(obj);x['id']='orderid' if table=='atlas_orders' else 'decisionid'
        x['status']='PENDING' if table=='atlas_orders' else x.get('status')
        self.rows.setdefault(table,[]).append(x)
        return [x]

class TestNavOrderIntent(unittest.TestCase):
    def test_creates_pending_intent_without_spending_cash(self):
        from app.engine import consider_nav_subscription
        now=dt.datetime(2026,11,11,12,40,tzinfo=TZ)
        db=FakeDB()
        funds={'FUND1':{'info':{'symbol':'FUND1','name':'Fondo MM','date':dt.date(2026,11,11),
              'nav':100,'r30':2.2,'manager':'Gerente X','buy_eligible':True},
              'instrument':{'symbol':'FUND1','id':'iid'}}}
        result=consider_nav_subscription(db,'pid',now,funds,True,[])
        self.assertIn('pendiente',result.lower())
        self.assertEqual(len(db.rows['atlas_orders']),1)
        self.assertEqual(db.rows['atlas_orders'][0]['status'],'PENDING')
        self.assertEqual(len(db.rows['atlas_nav_intents']),1)
        self.assertEqual(db.rows['atlas_portfolios'][0]['cash_ars'],10000000)
