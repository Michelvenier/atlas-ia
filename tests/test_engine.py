import unittest, datetime as dt
from app.engine import analysis,valid_intraday_quote,session_open
UTC=dt.timezone.utc
class TestMotor(unittest.TestCase):
 def test_historico_incompleto(self):
  with self.assertRaises(ValueError):analysis([(dt.datetime.now(UTC),100)]*5)
 def test_cotizacion_ausente(self):
  ok,why=valid_intraday_quote([],dt.datetime.now(UTC));self.assertFalse(ok)
 def test_cotizacion_antigua(self):
  now=dt.datetime.now(UTC);q=[(now-dt.timedelta(days=2),100)]
  self.assertFalse(valid_intraday_quote(q,now)[0])
 def test_fuera_sesion(self):
  self.assertFalse(session_open(dt.datetime(2026,11,7,15,0,tzinfo=UTC)))
 def test_analisis(self):
  now=dt.datetime.now(UTC);p=[(now-dt.timedelta(days=100-i),100+i/2) for i in range(90)]
  r=analysis(p);self.assertIn('rsi',r);self.assertTrue(0<=r['score']<=100)
if __name__=='__main__':unittest.main()
