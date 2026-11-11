import datetime as dt,unittest
from zoneinfo import ZoneInfo
from app.term_deposit import bank_offer
from app.engine import BUY_SCORE,QUOTE_MAX_AGE_S
TZ=ZoneInfo('America/Argentina/Buenos_Aires')
class TestActiveInvestment(unittest.TestCase):
 def setUp(self):self.now=dt.datetime(2026,11,11,13,0,tzinfo=TZ)
 def test_bank_offer_returns_recent_bank(self):
  offer,err=bank_offer({'results':[{'descripcionEntidad':'BANCO DE LA NACION ARGENTINA',
    'fechaInformacion':'2026-11-11','tasaEfectivaAnualMinima':22,
    'montoMinimoInvertir':1000,'plazoMinimoInvertirDias':30,'denominacion':'PF tradicional'}]},self.now)
  self.assertIsNone(err);self.assertEqual(offer['tea'],22)
 def test_bank_does_not_choose_stale(self):
  offer,err=bank_offer({'results':[{'descripcionEntidad':'BANCO GALICIA',
    'fechaInformacion':'2026-10-01','tasaEfectivaAnualMinima':30,'montoMinimoInvertir':0,
    'plazoMinimoInvertirDias':30}]},self.now)
  self.assertIsNone(offer);self.assertIn('Sin ofertas',err)
 def test_bank_does_not_choose_impossible_teas(self):
  offer,err=bank_offer({'results':[{'descripcionEntidad':'BANCO DE LA NACION ARGENTINA',
    'fechaInformacion':'2026-11-11','tasaEfectivaAnualMinima':10000,
    'montoMinimoInvertir':0,'plazoMinimoInvertirDias':30}]},self.now)
  self.assertIsNone(offer)
 def test_pilot_sizing_and_delay(self):
  self.assertLess(BUY_SCORE,78)
  self.assertGreater(QUOTE_MAX_AGE_S,900)
if __name__=='__main__':unittest.main()
