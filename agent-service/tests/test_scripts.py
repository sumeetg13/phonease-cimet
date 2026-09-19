import copy
import unittest
import uuid
from phonease.core import Supervisor, Store, parse_value
from phonease.script_registry import SCRIPTS, FIELDS, SECTIONS, validate_registry, pick, lines

def spoken(variants,message):
    return any(v in message for v in variants)

class ScriptTests(unittest.TestCase):
    def setUp(self):self.a=Supervisor(Store(':memory:'));self.s=self.a.start()
    def turn(self,text):self.s=self.a.turn(self.s['id'],text,uuid.uuid4().hex);return self.s
    def consent(self):
        self.turn('yes');self.turn('Alex Taylor');self.turn('yes')
    def test_section_intro_once_and_resume_skips_known(self):
        self.s=self.a.start(seed={'name':'Alex Taylor','postcode':'2000'})
        self.turn('yes');self.assertIn(SCRIPTS['messages']['resume'],self.s['message'])
        self.assertTrue(spoken(SECTIONS['supply']['intro'],self.s['message']));self.assertNotIn(FIELDS['postcode']['question'],self.s['message'])
        self.turn('gas');self.turn('yes');self.assertTrue(spoken(SECTIONS['property']['intro'],self.s['message']))
        self.turn('rent');self.turn('yes');self.assertFalse(spoken(SECTIONS['property']['intro'],self.s['message']))
    def test_opening_is_always_a_configured_variant(self):
        self.assertGreater(len(SCRIPTS['opening']),1)
        for _ in range(20):
            s=self.a.start()
            self.assertIn(s['message'],SCRIPTS['opening'])
    def test_lines_accepts_string_or_list_same_meaning(self):
        self.assertEqual(lines('hello','x'),['hello'])
        self.assertEqual(lines(['a','b'],'x'),['a','b'])
        with self.assertRaises(ValueError):lines([],'x')
        with self.assertRaises(ValueError):lines([''],'x')
    def test_pick_returns_a_member_of_the_list(self):
        for _ in range(20):self.assertIn(pick(['a','b','c']),['a','b','c'])
        self.assertEqual(pick('solo'),'solo')
    def test_registry_question_change_reaches_runtime(self):
        original=FIELDS['postcode']['question']
        try:
            FIELDS['postcode']['question']='Please tell me the supply postcode.'
            self.consent();self.assertIn('Please tell me the supply postcode.',self.s['message'])
        finally: FIELDS['postcode']['question']=original
    def test_clarification_specific_and_confirmation_from_registry(self):
        self.consent();self.turn('not sure');self.assertIn(FIELDS['postcode']['clarification'],self.s['message'])
        self.turn('2000');self.assertEqual(self.s['message'],FIELDS['postcode']['confirmation'].format(value='2000'))
    def test_aliases_capture_without_remote_model(self):
        for f,text,value in [('occupancy','I own it','own'),('fuel','power','electricity'),('solar','we have solar',True),('moving','I already live here',False)]:
            self.assertEqual(parse_value(f,text),value)
        self.assertIsNone(parse_value('solar','not sure'))
    def test_invalid_section_rejected(self):
        r=copy.deepcopy(SCRIPTS);r['fields'][0]['section']='unknown'
        with self.assertRaises(ValueError):validate_registry(r)
    def test_invalid_depends_on_rejected(self):
        r=copy.deepcopy(SCRIPTS)
        r['fields'][0]['depends_on']={'field':'no-such-field','equals':True}
        with self.assertRaises(ValueError):validate_registry(r)
    def test_name_field_is_asked_before_postcode(self):
        self.assertEqual(next(iter(FIELDS)),'name')
    def test_script_version_change_blocks_active_session(self):
        self.s['script_version']='energy-demo-v0';self.a.store.save(self.s)
        with self.assertRaisesRegex(ValueError,'Script version changed'):self.turn('yes')
    def test_operator_and_handoff_share_script(self):
        self.consent();self.assertEqual(self.s['active_script']['field'],FIELDS['postcode'])
        self.turn('human please');self.assertEqual(self.s['handoff']['script_version'],SCRIPTS['version'])
        self.assertEqual(self.s['handoff']['active_script']['field']['key'],'postcode')
    def test_retry_budget_from_registry(self):
        original=FIELDS['postcode']['max_failed_attempts']
        try:
            FIELDS['postcode']['max_failed_attempts']=1
            self.consent();self.turn('not sure');self.assertEqual(self.s['state'],'handoff_pending')
        finally:FIELDS['postcode']['max_failed_attempts']=original

if __name__=='__main__':unittest.main()
