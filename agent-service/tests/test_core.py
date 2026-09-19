import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
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
    def consent(self):
        # Grants consent, then answers and confirms the name question that now opens
        # every journey, so downstream tests can assume 'postcode' is asked next.
        self.turn('yes');self.turn('Alex Taylor');self.turn('yes')
    def complete(self):
        self.consent()
        # postcode, fuel, occupancy, moving, current_provider, has_bill(true)->bill_range, solar(false), concession_card
        for value in ['2000','electricity','rent','yes','agl','yes','under 200','no','no']:
            self.turn(value);self.turn('yes')
        self.turn('yes')
    def test_complete_and_receipt(self):
        self.complete();self.assertEqual(self.s['state'],'completed')
        self.assertEqual(self.s['receipt']['payload']['fields']['solar'],False)
        self.assertEqual(self.s['receipt']['payload']['fields']['current_provider'],'agl')
        self.assertEqual(self.s['receipt']['payload']['fields']['bill_range'],'under 200')
        self.assertNotIn('household_size',self.s['receipt']['payload']['fields'])
        self.assertNotIn('solar_size',self.s['receipt']['payload']['fields'])
        self.assertEqual(len(self.s['fields']),10)
    def test_no_bill_branch_asks_household_profile(self):
        self.consent()
        for value in ['2000','electricity','rent','yes','agl','no','one to two','no','yes','no','no','no']:
            self.turn(value);self.turn('yes')
        self.turn('yes')
        self.assertEqual(self.s['state'],'completed')
        fields=self.s['receipt']['payload']['fields']
        self.assertEqual(fields['household_size'],'one to two')
        self.assertFalse(fields['has_pool']);self.assertTrue(fields['has_ducted_ac']);self.assertFalse(fields['has_ev'])
        self.assertNotIn('bill_range',fields)
    def test_solar_true_asks_size(self):
        self.consent()
        for value in ['2000','electricity','rent','yes','agl','yes','under 200','yes','5 to 10kw','no']:
            self.turn(value);self.turn('yes')
        self.turn('yes')
        self.assertEqual(self.s['receipt']['payload']['fields']['solar_size'],'5 to 10kw')
    def test_changing_has_bill_clears_stale_bill_range(self):
        self.consent()
        for value in ['2000','electricity','rent','yes','agl','yes','under 200','no','no']:self.turn(value);self.turn('yes')
        self.assertEqual(self.s['state'],'review');self.assertIn('bill_range',self.s['fields'])
        self.turn('change recent bill available')
        self.assertNotIn('has_bill',self.s['fields']);self.assertNotIn('bill_range',self.s['fields'])
        self.turn('no');self.turn('yes')  # has_bill now false; the stale bill_range must not resurface
        self.turn('three to four');self.turn('yes')
        self.assertNotIn('bill_range',self.s['fields']);self.assertEqual(self.s['fields']['household_size']['value'],'three to four')
    def test_no_write_before_confirmation(self):
        self.consent();self.turn('2000');self.assertNotIn('postcode',self.s['fields'])
        self.assertEqual(self.s['pending']['value'],'2000')
    def test_name_field_rejects_bare_yes(self):
        self.turn('yes');self.turn('yes')
        self.assertIsNone(self.s['pending']);self.assertEqual(self.s['state'],'collecting')
    def test_name_asked_first_and_strips_filler(self):
        self.turn('yes');self.assertIn('full name',self.s['message'])
        self.turn("my name is jordan lee");self.assertEqual(self.s['pending']['value'],'Jordan Lee')
        self.turn('yes');self.assertEqual(self.s['fields']['name']['value'],'Jordan Lee')
        self.assertEqual(self.s['state'],'collecting');self.assertIn('postcode',self.s['message'].lower())
    def test_no_collection_before_consent(self):
        self.turn('2000');self.assertFalse(self.s['fields']);self.assertFalse(self.s['consent'])
        self.assertFalse(any(e['kind']=='caller' for e in self.s['events']))
    def test_consent_accepts_stacked_affirmations(self):
        self.turn('yeah, sure');self.assertTrue(self.s['consent']);self.assertEqual(self.s['state'],'collecting')
    def test_consent_accepts_synonym_phrases(self):
        for phrase in ['of course','definitely','why not','sounds good','sure thing']:
            s=self.agent.start('synthetic-'+phrase.replace(' ','-'))
            s=self.agent.turn(s['id'],phrase,'e-'+phrase)
            self.assertTrue(s['consent'],phrase);self.assertEqual(s['state'],'collecting',phrase)
    def test_consent_not_really_declines(self):
        self.turn('not really');self.assertEqual(self.s['state'],'declined')
    def test_boolean_field_accepts_synonym(self):
        self.consent()
        for v in ['2000','electricity','rent']: self.turn(v);self.turn('yes')
        self.turn('of course');self.assertEqual(self.s['pending']['value'],True)
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
        s=self.agent.start('synthetic-resume',{'name':'Alex Taylor','postcode':'3000','fuel':'both'})
        s=self.agent.turn(s['id'],'yes','c');self.assertIn('own or rent',s['message'])
    def test_model_cannot_submit_invalid_value(self):
        class Fake:
            def analyze(self,*args): return {'value':'not-a-postcode','signals':[],'sentiment':'neutral','confirmation':None}
        self.agent.model=Fake();self.consent();self.turn('something');self.assertNotIn('postcode',self.s['fields']);self.assertEqual(self.s['state'],'collecting')
    def test_model_confirms_paraphrase(self):
        class Fake:
            def analyze(self,*args): return {'value':None,'signals':[],'sentiment':'neutral','confirmation':{'answer':'yes','confidence':0.9}}
        self.consent();self.turn('2000')
        self.agent.model=Fake();self.turn("yeah that's totally right, thanks")
        self.assertEqual(self.s['fields']['postcode']['value'],'2000')
    def test_model_low_confidence_confirmation_still_repairs(self):
        class Fake:
            def analyze(self,*args): return {'value':None,'signals':[],'sentiment':'neutral','confirmation':{'answer':'yes','confidence':0.4}}
        self.consent();self.turn('2000')
        self.agent.model=Fake();self.turn("hmm i guess so maybe")
        self.assertEqual(self.s['state'],'confirming')
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
        for v in ['2000','gas','own','yes','agl','yes','under 200','no','no']:self.turn(v);self.turn('yes')
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
    def test_default_voice_is_neural(self):
        s=Supervisor(Store(':memory:')).start('synthetic-phone')
        root=ET.fromstring(Twilio().response(s))
        self.assertEqual(root.find('Gather/Say').attrib['voice'],'Polly.Olivia-Neural')
    def test_voice_configurable_and_optional(self):
        s=Supervisor(Store(':memory:')).start('synthetic-phone')
        with patch.dict(os.environ,{'TWILIO_VOICE':'Polly.Russell'}):
            self.assertEqual(ET.fromstring(Twilio().response(s)).find('Gather/Say').attrib['voice'],'Polly.Russell')
        with patch.dict(os.environ,{'TWILIO_VOICE':''}):
            self.assertNotIn('voice',ET.fromstring(Twilio().response(s)).find('Gather/Say').attrib)

class CallRecordTests(unittest.TestCase):
    """Live notes, the end-of-call summary and the receipt that carries the transcript."""
    def setUp(self):
        self.agent=Supervisor(Store(':memory:')); self.s=self.agent.start('synthetic-record')
    def turn(self,text):
        self.s=self.agent.turn(self.s['id'],text,uuid.uuid4().hex); return self.s
    def texts(self):
        return [n['text'] for n in self.s['notes']]
    def complete(self):
        self.turn('yes');self.turn('Alex Taylor');self.turn('yes')
        for value in ['2000','electricity','rent','yes','agl','yes','under 200','no','no']:
            self.turn(value);self.turn('yes')
        self.turn('yes')
    def test_notes_are_written_as_the_call_happens(self):
        self.assertEqual(self.texts(),['Recovery call opened on a synthetic lead.'])
        self.turn('yes')
        self.assertIn('Consent given to continue and store the transcript. No audio is recorded.',self.texts())
        self.turn('Alex Taylor');self.turn('yes')
        self.assertIn('Caller name: Alex Taylor (confirmed by the caller)',self.texts())
        self.turn('2000');self.turn('no')
        self.assertIn('Supply postcode: the read-back was wrong; asked again.',self.texts())
    def test_a_carried_over_answer_is_noted_before_the_caller_speaks(self):
        s=self.agent.start('synthetic-resume',{'postcode':'2000'})
        self.assertIn('Supply postcode: 2000 (carried over from the earlier journey)',[n['text'] for n in s['notes']])
    def test_what_the_caller_raised_is_noted_once_and_never_quoted(self):
        self.turn('yes')
        self.turn("I can't afford my energy bills")
        self.turn("I can't afford my energy bills")
        concerns=[n['text'] for n in self.s['notes'] if n['kind']=='concern']
        self.assertEqual(concerns,['Raised hardship, a billing dispute or a vulnerability concern.'])
        self.assertNotIn('afford',' '.join(self.texts()))
    def test_a_concern_before_consent_is_noted_without_storing_the_utterance(self):
        self.turn('Where did you get my number?')
        self.assertIn('Asked where their details came from.',self.texts())
        self.assertEqual([e for e in self.s['events'] if e['kind']=='caller'],[])
    def test_submission_asks_first_and_the_receipt_carries_the_transcript_and_notes(self):
        self.turn('yes');self.turn('Alex Taylor');self.turn('yes')
        for value in ['2000','electricity','rent','yes','agl','yes','under 200','no','no']:
            self.turn(value);self.turn('yes')
        self.assertEqual(self.s['state'],'review')
        self.assertIn('submit these details for further processing',self.s['message'])
        self.assertIsNone(self.s['receipt'])          # Nothing is submitted before the caller agrees.
        self.turn('yes')
        payload=self.s['receipt']['payload']
        roles=[t['role'] for t in payload['transcript']]
        self.assertEqual(sorted(set(roles)),['assistant','caller'])
        self.assertIn('Alex Taylor',[t['text'] for t in payload['transcript']])
        # The consenting turn itself precedes consent, so it is never stored.
        self.assertNotIn('yes',[t['text'] for t in payload['transcript'][:2]])
        self.assertIn('Caller name: Alex Taylor (confirmed by the caller)',[n['text'] for n in payload['notes']])
        self.assertIn('Details submitted for further processing. Receipt '+self.s['receipt']['id']+' (local-mock).',self.texts())
    def test_the_summary_is_available_after_the_call_ends(self):
        self.complete()
        summary=self.s['summary']
        self.assertEqual(summary['outcome'],'completed')
        self.assertEqual([f['value'] for f in summary['fields'] if f['key']=='postcode'],['2000'])
        self.assertEqual(summary['fields'][0]['label'],'Caller name')   # Script order, not answer order.
        self.assertEqual(summary['receipt']['id'],self.s['receipt']['id'])
        self.assertEqual(summary['transcript'][-1]['role'],'assistant')
        self.assertGreater(len(summary['notes']),5)
    def test_a_declined_call_still_produces_a_summary_and_no_receipt(self):
        self.turn('no')
        self.assertEqual(self.s['state'],'declined')
        self.assertIsNone(self.s['summary']['receipt'])
        self.assertIn('Caller declined; nothing was submitted.',self.texts())
        self.assertEqual(self.s['summary']['outcome'],'declined')
    def test_a_handover_is_noted_and_summarized_when_the_specialist_accepts(self):
        self.turn('yes');self.turn("I'd like to speak to a human")
        self.assertIn('Handover to an energy specialist: explicit human request.',self.texts())
        self.s=self.agent.accept(self.s['id'],'demo-human')
        self.assertEqual(self.s['summary']['outcome'],'human')
        self.assertEqual(self.s['summary']['handoff_reason'],'explicit_human_request')
        self.assertIn('Energy specialist accepted the call; the AI stopped. Nothing was submitted.',self.texts())
    def test_a_payment_utterance_is_withheld_from_the_transcript_it_leaves_behind(self):
        self.turn('yes');self.turn('my card number is 4111 1111 1111 1111')
        self.s=self.agent.accept(self.s['id'],'demo-human')   # The record is written when the call ends.
        spoken=[t['text'] for t in self.s['summary']['transcript'] if t['role']=='caller']
        self.assertIn('[payment-related utterance withheld]',spoken)
        self.assertNotIn('4111',' '.join(spoken))

if __name__=='__main__':unittest.main()
