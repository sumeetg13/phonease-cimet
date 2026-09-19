"""Twilio turn-based speech adapter. Not a full-duplex streaming implementation."""
import base64
import hashlib
import hmac
import json
import os
import urllib.parse
import urllib.request
from xml.etree.ElementTree import Element, SubElement, tostring
from .core import TERMINAL, FIELDS, display

def xml(root): return tostring(root,encoding='unicode')
def say(root,text): SubElement(root,'Say',{'language':'en-AU'}).text=text

def signature_valid(url, params, signature, token):
    # Form params preserve multiple values; Twilio sorts unique values for each key.
    material=url+''.join(k+v for k in sorted(params) for v in sorted(set(params[k])))
    expected=base64.b64encode(hmac.new(token.encode(),material.encode(),hashlib.sha1).digest()).decode()
    return bool(signature and token) and hmac.compare_digest(expected,signature)

class Twilio:
    def __init__(self):
        self.base=os.getenv('PUBLIC_BASE_URL','').rstrip('/')
        self.token=os.getenv('TWILIO_AUTH_TOKEN','')
        self.account=os.getenv('TWILIO_ACCOUNT_SID','')
        self.human=os.getenv('HUMAN_TEST_NUMBER','')
        self.allowed=set(x.strip() for x in os.getenv('TEST_NUMBERS','').split(',') if x.strip())

    def url(self,path,s,**extra):
        return self.base+path+'?'+urllib.parse.urlencode({'sid':s['id'],**extra})

    def response(self,s):
        root=Element('Response')
        if s['state']=='handoff_pending':
            say(root,s['message'])
            if not self.human or self.human not in self.allowed:
                # Execute fallback via signed webhook, so durable state matches speech.
                SubElement(root,'Redirect',{'method':'POST'}).text=self.url('/twilio/unavailable',s)
            else:
                dial=SubElement(root,'Dial',{'answerOnBridge':'true','timeout':'20','action':self.url('/twilio/dial-result',s),'method':'POST'})
                SubElement(dial,'Number',{'url':self.url('/twilio/whisper',s),'method':'POST'}).text=self.human
        elif s['state'] in TERMINAL:
            say(root,s['message']); SubElement(root,'Hangup')
        else:
            gather=SubElement(root,'Gather',{'input':'speech','language':'en-AU','speechTimeout':'auto',
                'timeout':'7','actionOnEmptyResult':'true','method':'POST',
                'action':self.url('/twilio/turn',s,revision=s['revision'])})
            say(gather,s['message'])
        return xml(root)

    def whisper(self,s):
        root=Element('Response')
        h=s['handoff']
        summary='; '.join(FIELDS[k]['label']+': '+display(v['value']) for k,v in h['confirmed_fields'].items()) or 'No confirmed fields'
        gather=SubElement(root,'Gather',{'input':'dtmf','numDigits':'1','timeout':'10','actionOnEmptyResult':'true',
            'action':self.url('/twilio/accept',s),'method':'POST'})
        say(gather,'Synthetic Phonease Energy recovery. Reason: '+h['reason'].replace('_',' ')+'. '+summary+
            '. Consent recorded: '+str(h['consent'])+'. Please do not ask the customer to repeat confirmed details. Press 1 to accept, or 2 to decline.')
        SubElement(root,'Hangup')
        return xml(root)

    def dial(self,s,number):
        if os.getenv('TELEPHONY_ENABLED')!='true': raise ValueError('Telephone calling is disabled')
        if not self.base.startswith('https://') or not self.token or not self.account: raise ValueError('Configure HTTPS URL and Twilio credentials')
        if number not in self.allowed: raise ValueError('Destination must be an approved test number')
        fields={'To':number,'From':os.environ['TWILIO_FROM_NUMBER'],
                'Url':self.url('/twilio/start',s),'Method':'POST','Record':'false'}
        auth=base64.b64encode((self.account+':'+self.token).encode()).decode()
        req=urllib.request.Request('https://api.twilio.com/2010-04-01/Accounts/'+self.account+'/Calls.json',
            data=urllib.parse.urlencode(fields).encode(),headers={'Authorization':'Basic '+auth})
        with urllib.request.urlopen(req,timeout=8) as r: result=json.load(r)
        return {'call_sid':result['sid'],'status':result['status']}
