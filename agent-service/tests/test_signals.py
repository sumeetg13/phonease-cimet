import json
import unittest
import uuid
from phonease.core import Supervisor, Store
from phonease.signals import detect, validate_analysis

class StubModel:
    def __init__(self, labels=(), severity='medium', sentiment='neutral', value=None):
        self.labels=labels;self.severity=severity;self.sentiment=sentiment;self.value=value;self.calls=[]
    def analyze(self,field,text,context):
        self.calls.append((field,text,context))
        return {'value':self.value,'sentiment':self.sentiment,'confirmation':None,
            'signals':[{'label':label,'severity':self.severity,'evidence':text} for label in self.labels]}

class SignalTests(unittest.TestCase):
    def setUp(self):
        self.a=Supervisor(Store(':memory:'));self.s=self.a.start()
    def turn(self,text):
        self.s=self.a.turn(self.s['id'],text,uuid.uuid4().hex);return self.s
    def test_local_categories(self):
        samples={'privacy':'Where did you get my number?', 'distress':"I'm overwhelmed",
                 'accessibility':"I'm hard of hearing", 'language':"I don't speak English",
                 'sensitive':"I was overcharged", 'technical':'The line is breaking up',
                 'confusion':"I don't understand"}
        for label,text in samples.items():
            with self.subTest(label=label): self.assertIn(label,[x['label'] for x in detect(text)])
    def test_negated_human_request(self):
        self.assertNotIn('human',[x['label'] for x in detect("I don't need a human")])
        self.assertIn('human',[x['label'] for x in detect("I'm not angry, but get me a human")])
    def test_negated_anger(self):
        self.assertNotIn('anger',[x['label'] for x in detect("I'm not angry")])
    def test_no_remote_model_before_consent(self):
        self.a.model=StubModel();self.turn('maybe');self.assertFalse(self.a.model.calls)
        self.assertEqual(self.s['analysis']['model_status'],'consent_required')
    def test_contextual_model_during_confirmation(self):
        self.turn('yes');self.turn('Alex Taylor');self.turn('yes');self.turn('2000')
        self.a.model=StubModel(['human'])
        self.turn('Could a colleague take it from here?')
        self.assertEqual(self.s['state'],'handoff_pending')
        self.assertEqual(self.a.model.calls[0][2]['stage'],'confirming')
        self.assertIsNone(self.a.model.calls[0][0]);self.assertNotIn('postcode',self.s['fields'])
    def test_model_during_review(self):
        self.s=self.a.start(seed={'name':'Alex Taylor','postcode':'2000','fuel':'gas','occupancy':'own','moving':False,
            'current_provider':'agl','has_bill':True,'bill_range':'under 200','solar':False,'concession_card':False})
        self.turn('yes');self.assertEqual(self.s['state'],'review')
        self.a.model=StubModel(['privacy']);self.turn('Who else will see these answers?')
        self.assertEqual(self.s['state'],'handoff_pending');self.assertIsNone(self.s['receipt'])
    def test_model_dnc_while_waiting(self):
        self.turn('yes');self.turn('human please');self.a.model=StubModel(['dnc'])
        self.turn('Never ring this line again')
        self.assertEqual(self.s['state'],'suppressed');self.assertTrue(self.a.store.suppressed(self.s['lead_id']))
    def test_multiple_signals_dnc_wins(self):
        self.turn('yes');self.a.model=StubModel(['anger','human','dnc'],sentiment='negative')
        self.turn('No further ringing from your team; get a colleague to sort this mess')
        self.assertEqual(self.s['state'],'suppressed');self.assertEqual(len(self.s['analysis']['signals']),3)
    def test_negative_sentiment_alone_does_not_transfer(self):
        self.turn('yes');self.turn('Alex Taylor');self.turn('yes')
        self.a.model=StubModel(sentiment='negative',value='2000')
        self.turn('My previous retailer treated me terribly; the postcode is 2000')
        self.assertEqual(self.s['state'],'confirming');self.assertEqual(self.s['analysis']['sentiment'],'negative')
    def test_model_payment_redacted_before_storage(self):
        self.turn('yes');self.a.model=StubModel(['payment'])
        secret='The plastic has four one one one printed on it'
        self.turn(secret)
        self.assertEqual(self.s['handoff']['reason'],'payment_boundary')
        self.assertNotIn(secret,json.dumps(self.s));self.assertNotIn('four one',json.dumps(self.s))
    def test_known_payment_never_reaches_model(self):
        self.turn('yes');self.a.model=StubModel();self.turn('My credit card is four one one one')
        self.assertFalse(self.a.model.calls)
    def test_severe_semantic_frustration_transfers_once(self):
        self.turn('yes');self.a.model=StubModel(['anger'],severity='high',sentiment='negative')
        self.turn('Enough of this nonsense')
        self.assertEqual(self.s['handoff']['reason'],'frustration')
        self.assertEqual(self.s['handoff']['signals'][-1]['source'],'model')
    def test_mild_frustration_expires_outside_window(self):
        self.turn('yes');self.turn('I am annoyed');self.turn('Alex Taylor');self.turn('yes');self.turn('I am annoyed')
        self.assertEqual(self.s['state'],'collecting');self.assertEqual(self.s['anger_count'],1)
    def test_semantic_confusion_repairs_then_hands_over(self):
        self.turn('yes');self.a.model=StubModel(['confusion']);self.turn('That went over my head')
        self.assertEqual(self.s['state'],'collecting');self.turn('That went over my head')
        self.assertEqual(self.s['state'],'handoff_pending')
    def test_invented_evidence_rejected(self):
        with self.assertRaises(ValueError):
            validate_analysis({'value':None,'sentiment':'neutral','signals':[{'label':'human','severity':'high','evidence':'invented'}]},'yes')
    def test_model_failure_blocks_final_submission(self):
        self.s=self.a.start(seed={'name':'Alex Taylor','postcode':'2000','fuel':'gas','occupancy':'own','moving':False,
            'current_provider':'agl','has_bill':True,'bill_range':'under 200','solar':False,'concession_card':False})
        self.turn('yes')
        class Broken:
            def analyze(self,*args): raise TimeoutError()
        self.a.model=Broken();self.turn('yes');self.assertEqual(self.s['handoff']['reason'],'model_unavailable');self.assertIsNone(self.s['receipt'])

if __name__=='__main__': unittest.main()
