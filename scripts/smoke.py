#!/usr/bin/env python3
"""Exercise the public API, PostgreSQL state, and optionally a real model call."""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid
from setup import read_env, ROOT

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Make one paid model request after consent')
    parser.add_argument('--url')
    args=parser.parse_args()
    env=read_env(ROOT/'.env')
    url=args.url or 'http://127.0.0.1:'+os.getenv('UI_PORT',env.get('UI_PORT','5173'))
    token=os.getenv('PHONEASE_API_TOKEN',env['PHONEASE_API_TOKEN'])
    def request(path,body=None,expected=200,auth=True):
        headers={'Content-Type':'application/json'}
        if auth: headers['Authorization']='Bearer '+token
        req=urllib.request.Request(url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=30) as response: code=response.status; result=json.load(response)
        except urllib.error.HTTPError as error:
            code=error.code; result=json.loads(error.read())
        if code!=expected: raise AssertionError(f'{path}: expected {expected}, got {code}; {result}')
        return result
    def start(seed=None,lead=None): return request('/api/sessions',{'lead_id':lead or 'synthetic-smoke-'+uuid.uuid4().hex,'seed':seed or {}},201)
    def turn(s,text,event=None,expected=200,revision=None):
        return request('/api/turn',{'session_id':s['id'],'text':text,'event_id':event or uuid.uuid4().hex,'revision':s['revision'] if revision is None else revision},expected)
    request('/health',auth=False)
    request('/api/scripts',auth=False,expected=401)
    assert len(request('/api/scripts')['fields'])==5
    if args.live:
        s=turn(start(),'yes')
        s=turn(s,'Could a colleague take it from here?')
        assert s['analysis']['source']=='model',s['analysis']
        assert s['analysis']['model_status']=='analyzed',s['analysis']
        assert s['state']=='handoff_pending',s['state']
        print('PASS: live LangChain/OpenAI analysis → LangGraph policy → Spring Boot → PostgreSQL handover')
        return
    s=start()
    if s['mode']=='model-assisted': raise SystemExit('Offline smoke tests require OPENAI_API_KEY= for the agent. Use --live for a small paid test.')
    event=uuid.uuid4().hex
    s=turn(s,'yes',event)
    duplicate=turn(s,'yes',event,revision=0)
    assert duplicate['revision']==s['revision']
    turn(s,'2000',expected=400,revision=0)
    for value in ['2000','electricity','rent','no','no']:
        s=turn(s,value); assert s['state']=='confirming',s['state']
        s=turn(s,'yes')
    assert s['state']=='review'
    s=turn(s,'change postcode'); s=turn(s,'3000'); s=turn(s,'yes'); s=turn(s,'yes')
    assert s['state']=='completed' and s['receipt']['payload']['fields']['postcode']=='3000'
    assert request('/api/sessions/'+s['id'])['receipt']['id']==s['receipt']['id']
    assert turn(s,'yes')['receipt']['id']==s['receipt']['id']
    print('PASS: confirmation, correction, submission, persistent receipt, duplicate and stale turn protection')
    lead='synthetic-smoke-'+uuid.uuid4().hex
    s=turn(start(lead=lead),'stop calling me'); assert s['state']=='suppressed'
    request('/api/sessions',{'lead_id':lead},400)
    print('PASS: persistent suppression blocks a new session')
    s=turn(start(),'yes'); s=turn(s,'my credit card is 4111 1111 1111 1111')
    assert s['handoff']['reason']=='payment_boundary' and '4111' not in json.dumps(request('/api/sessions/'+s['id']))
    s=request('/api/unavailable',{'session_id':s['id']}); assert s['state']=='callback'
    s=turn(start({'postcode':'2000'}),'yes'); s=turn(s,'human please')
    assert s['handoff']['confirmed_fields']['postcode']['value']=='2000'
    s=request('/api/accept',{'session_id':s['id']}); assert s['state']=='human'
    assert turn(s,'gas')['state']=='human'
    request('/api/dial',{'session_id':start()['id'],'number':'+61000000000'},400)
    print('PASS: payment withholding, resume context, handover acceptance/unavailability, AI freeze and disabled telephony')
    print('All HTTP/PostgreSQL smoke tests passed. Synthetic smoke sessions remain available for inspection.')

if __name__=='__main__': main()
