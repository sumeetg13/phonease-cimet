#!/usr/bin/env python3
"""One paid neural speech request; no phone call. Uses the existing private env."""
import json
import os
import urllib.error
import urllib.request
from setup import ROOT, read_env

def main():
    env=read_env(ROOT/'.env')
    base='http://127.0.0.1:'+os.getenv('UI_PORT',env.get('UI_PORT','5173'))
    token=os.getenv('PHONEASE_API_TOKEN',env['PHONEASE_API_TOKEN'])
    def request(path,body,expected=200,auth=True):
        headers={'Content-Type':'application/json'}
        if auth: headers['Authorization']='Bearer '+token
        req=urllib.request.Request(base+path,data=json.dumps(body).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=25) as response:
                status=response.status; content=response.read(); headers=response.headers
        except urllib.error.HTTPError as error:
            status=error.code; content=error.read(); headers=error.headers
        assert status==expected, f'{path}: expected {expected}, got {status}'
        return content,headers
    request('/api/speech',{},401,False)
    content,_=request('/api/sessions',{},201)
    session=json.loads(content)
    identity={'session_id':session['id'],'revision':session['revision']}
    request('/api/speech',{**identity,'revision':-1},400)
    audio,headers=request('/api/speech',identity)
    assert headers.get_content_type()=='audio/mpeg'
    assert headers.get('Cache-Control')=='no-store'
    assert len(audio)>1000 and (audio.startswith(b'ID3') or (audio[0]==255 and audio[1]&224==224)), 'Invalid MP3'
    print(f'PASS: authenticated live neural TTS returned {len(audio)} MP3 bytes; stale revisions and unauthenticated requests rejected.')

if __name__=='__main__': main()
