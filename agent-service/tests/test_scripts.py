import copy
import unittest
import uuid
from phonease.core import Supervisor, Store, parse_value
from phonease.script_registry import SCRIPTS, FIELDS, SECTIONS, validate_registry

class ScriptTests(unittest.TestCase):
    def setUp(self):self.a=Supervisor(Store(':memory:'));self.s=self.a.start()
    def turn(self,text):self.s=self.a.turn(self.s['id'],text,uuid.uuid4().hex);return self.s
    def test_section_intro_once_and_resume_skips_known(self):
        self.s=self.a.start(seed={'postcode':'2000'})
        self.turn('yes');self.assertIn(SCRIPTS['messages']['resume'],self.s['message'])
        self.assertIn(SECTIONS['supply']['intro'],self.s['message']);self.assertNotIn(FIELDS['postcode']['question'],self.s['message'])
        self.turn('gas');self.turn('yes');self.assertIn(SECTIONS['property']['intro'],self.s['message'])
        self.turn('rent');self.turn('yes');self.assertNotIn(SECTIONS['property']['intro'],self.s['message'])
    def test_registry_question_change_reaches_runtime(self):
        original=FIELDS['postcode']['question']
        try:
            FIELDS['postcode']['question']='Please tell me the supply postcode.'
            self.turn('yes');self.assertIn('Please tell me the supply postcode.',self.s['message'])
        finally: FIELDS['postcode']['question']=original
    def test_clarification_specific_and_confirmation_from_registry(self):
        self.turn('yes');self.turn('not sure');self.assertIn(FIELDS['postcode']['clarification'],self.s['message'])
        self.turn('2000');self.assertEqual(self.s['message'],FIELDS['postcode']['confirmation'].format(value='2000'))
    def test_aliases_capture_without_remote_model(self):
        for f,text,value in [('occupancy','I own it','own'),('fuel','power','electricity'),('solar','we have solar',True),('moving','I already live here',False)]:
            self.assertEqual(parse_value(f,text),value)
        self.assertIsNone(parse_value('solar','not sure'))
    def test_invalid_section_rejected(self):
        r=copy.deepcopy(SCRIPTS);r['fields'][0]['section']='unknown'
        with self.assertRaises(ValueError):validate_registry(r)
    def test_script_version_change_blocks_active_session(self):
        self.s['script_version']='energy-demo-v0';self.a.store.save(self.s)
        with self.assertRaisesRegex(ValueError,'Script version changed'):self.turn('yes')
    def test_operator_and_handoff_share_script(self):
        self.turn('yes');self.assertEqual(self.s['active_script']['field'],FIELDS['postcode'])
        self.turn('human please');self.assertEqual(self.s['handoff']['script_version'],SCRIPTS['version'])
        self.assertEqual(self.s['handoff']['active_script']['field']['key'],'postcode')
    def test_retry_budget_from_registry(self):
        original=FIELDS['postcode']['max_failed_attempts']
        try:
            FIELDS['postcode']['max_failed_attempts']=1
            self.turn('yes');self.turn('not sure');self.assertEqual(self.s['state'],'handoff_pending')
        finally:FIELDS['postcode']['max_failed_attempts']=original

if __name__=='__main__':unittest.main()
