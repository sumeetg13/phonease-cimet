import json
import tempfile
import unittest
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET
from phonease.core import Supervisor, Store, FIELDS, signals
from phonease.telephony import Twilio, signature_valid
import base64
import hashlib
import hmac

class FlowTests(unittest.TestCase):
    def setUp(self):
        self.agent=Supervisor(Store(':memory:')); self.s=self.agent.start('synthetic-test')
    def turn(self,text,confidence=None, eid=None):
        self.s=self.agent.turn(self.s['id'],text,eid or uuid.uuid4().hex,confidence);return self.s
    def consent(self): self.turn('yes')
    def complete(self):
        self.consent()
        for value in ['2000','electricity','rent','no','yes']:
            self.turn(value);self.turn('yes')
        self.turn('yes')
    def test_complete_and_receipt(self):
        self.complete();self.assertEqual(self.s['state'],'completed')
        self.assertEqual(self.s['receipt']['payload']['fields']['solar'],False)
        self.assertEqual(len(self.s['fields']),5)
    def test_no_write_before_confirmation(self):
        self.consent();self.turn('2000');self.assertNotIn('postcode',self.s['fields'])
        self.assertEqual(self.s['pending']['value'],'2000')
    def test_no_collection_before_consent(self):
        self.turn('2000');self.assertFalse(self.s['fields']);self.assertFalse(self.s['consent'])
        self.assertFalse(any(e['kind']=='caller' for e in self.s['events']))
    def test_consent_no_ends(self):
        self.turn('no');self.assertEqual(self.s['state'],'declined')
    def test_no_thanks_ends(self):
        self.turn('no thanks');self.assertEqual(self.s['state'],'declined')
    def test_consent_two_ambiguous_turns_handoff(self):
        self.turn('maybe');self.turn('maybe');self.assertEqual(self.s['state'],'handoff_pending')
    def test_dnc_dominates_human_and_anger(self):
        self.turn('Stop calling me. I am angry. Get a human.');self.assertEqual(self.s['state'],'suppressed')
        with self.assertRaises(ValueError): self.agent.start('synthetic-test')
    def test_dnc_blocks_same_lead(self):
        store=Store();a=Supervisor(store);s=a.start('synthetic-persist')
        a.turn(s['id'],'stop calling','event')
        with self.assertRaises(ValueError): Supervisor(store).start('synthetic-persist')
    def test_busy_no_fake_booking(self):
        self.turn("I'm busy");self.assertEqual(self.s['state'],'callback');self.assertIn('No callback time',self.s['message'])
    def test_low_confidence_twice(self):
        self.consent();self.turn('2000',.2);self.turn('2000',.2)
        self.assertEqual(self.s['handoff']['reason'],'two_failed_attempts:postcode')
    def test_missing_confidence_not_zero(self):
        self.consent();self.turn('2000');self.assertEqual(self.s['state'],'confirming')
    def test_field_repair(self):
        self.consent();self.turn('2000');self.turn('no');self.turn('3000');self.turn('yes')
        self.assertEqual(self.s['fields']['postcode']['value'],'3000')
    def test_bad_field_twice(self):
        self.consent();self.turn('banana');self.turn('banana');self.assertEqual(self.s['state'],'handoff_pending')
    def test_payment_redacted(self):
        self.consent();self.turn('my card number is 4111 1111 1111 1111')
        self.assertEqual(self.s['handoff']['reason'],'payment_boundary')
        self.assertNotIn('4111',json.dumps(self.s));self.assertNotIn('my card number',json.dumps(self.s))
    def test_spoken_card_redacted(self):
        self.consent();self.turn('my credit card is four one one one')
        self.assertNotIn('four one',json.dumps(self.s))
    def test_sensitive(self):
        self.consent();self.turn('I need life support');self.assertEqual(self.s['handoff']['reason'],'sensitive_or_vulnerable')
    def test_no_advice(self):
        self.consent();self.turn('Which plan should I choose?');self.assertEqual(self.s['state'],'handoff_pending')
    def test_frustration(self):
        self.consent();self.turn('This is frustrating and ridiculous');self.turn('I am angry')
        self.assertEqual(self.s['handoff']['reason'],'frustration')
    def test_handoff_packet_and_freeze(self):
        self.consent();self.turn('2000');self.turn('yes');self.turn('human please')
        self.assertEqual(self.s['handoff']['confirmed_fields']['postcode']['value'],'2000')
        self.turn('gas');self.assertNotIn('fuel',self.s['fields'])
        self.s=self.agent.accept(self.s['id'],'Test human');self.turn('gas');self.assertEqual(self.s['state'],'human')
    def test_dnc_during_wait(self):
        self.consent();self.turn('human please');self.turn('stop calling me');self.assertEqual(self.s['state'],'suppressed')
    def test_unavailable(self):
        self.turn('human please');self.s=self.agent.unavailable(self.s['id']);self.assertEqual(self.s['state'],'callback')
    def test_idempotent_turn(self):
        self.turn('yes',eid='fixed');rev=self.s['revision'];self.turn('yes',eid='fixed');self.assertEqual(self.s['revision'],rev)
    def test_stale_turn_rejected(self):
        self.consent()
        with self.assertRaises(ValueError): self.agent.turn(self.s['id'],'2000','stale',revision=0)
    def test_submission_idempotent(self):
        self.complete();r=self.s['receipt']['id'];self.turn('yes');self.assertEqual(self.s['receipt']['id'],r)
        self.assertEqual(len(self.agent.store.receipts),1)
    def test_seed_resume(self):
        s=self.agent.start('synthetic-resume',{'postcode':'3000','fuel':'both'})
        s=self.agent.turn(s['id'],'yes','c');self.assertIn('own or rent',s['message'])
    def test_model_cannot_submit_invalid_value(self):
        class Fake:
            def analyze(self,*args): return {'value':'not-a-postcode','signals':[],'sentiment':'neutral'}
        self.agent.model=Fake();self.consent();self.turn('something');self.assertFalse(self.s['fields']);self.assertEqual(self.s['state'],'collecting')
    def test_model_timeout_handoff(self):
        class Fake:
            def analyze(self,*args): raise TimeoutError()
        self.agent.model=Fake();self.consent();self.turn('something');self.assertEqual(self.s['handoff']['reason'],'model_unavailable')
    def test_spoken_digits(self):
        self.consent();self.turn('two zero zero zero');self.assertEqual(self.s['pending']['value'],'2000')
    def test_nan_confidence(self):
        with self.assertRaises(ValueError): self.turn('yes',float('nan'))
    def test_unique_default_leads(self): self.assertNotEqual(self.agent.start()['lead_id'],self.agent.start()['lead_id'])
    def test_review_correction(self):
        self.consent()
        for v in ['2000','gas','own','no','no']:self.turn(v);self.turn('yes')
        self.turn('change postcode');self.assertNotIn('postcode',self.s['fields'])
        self.turn('3000');self.turn('yes');self.turn('yes')
        self.assertEqual(self.s['receipt']['payload']['fields']['postcode'],'3000')

class TelephoneTests(unittest.TestCase):
    def test_signature(self):
        url='https://example.test/twilio/turn?sid=123';params={'CallSid':['CA123'],'SpeechResult':['yes']}
        value=url+'CallSidCA123SpeechResultyes'
        sig=base64.b64encode(hmac.new(b'secret',value.encode(),hashlib.sha1).digest()).decode()
        self.assertTrue(signature_valid(url,params,sig,'secret'))
        self.assertFalse(signature_valid(url,{'CallSid':['evil']},sig,'secret'))
    def test_gather_uses_revision_and_timeout(self):
        s=Supervisor(Store(':memory:')).start('synthetic-phone');root=ET.fromstring(Twilio().response(s))
        g=root.find('Gather');self.assertEqual(g.attrib['actionOnEmptyResult'],'true');self.assertIn('revision=0',g.attrib['action'])
    def test_whisper_explicit_acceptance(self):
        a=Supervisor(Store(':memory:'));s=a.start('synthetic-phone');s=a.turn(s['id'],'human','h')
        root=ET.fromstring(Twilio().whisper(s));self.assertEqual(root.find('Gather').attrib['numDigits'],'1')
        self.assertIn('Press 1',root.find('Gather/Say').text)
    def test_no_human_number_routes_fallback(self):
        a=Supervisor(Store(':memory:'));s=a.start('synthetic-phone');s=a.turn(s['id'],'human','h')
        t=Twilio();t.human='';self.assertIn('/twilio/unavailable',t.response(s))

if __name__=='__main__':unittest.main()
