#!/usr/bin/env python3
"""Create local configuration without overwriting existing secrets."""
import argparse
import os
from pathlib import Path
import secrets

ROOT=Path(__file__).resolve().parents[1]

def read_env(path):
    values={}
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        key,sep,value=line.partition('=')
        if sep:
            value=value.strip()
            if len(value)>1 and value[0]==value[-1] and value[0] in "'\"": value=value[1:-1]
            values[key.removeprefix('export ').strip()]=value
    return values

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference-env',type=Path,help='Optionally reuse only OPENAI_API_KEY from an existing local .env')
    args=parser.parse_args()
    path=ROOT/'.env'
    if path.exists():
        print('.env already exists; left unchanged.'); return
    values=read_env(ROOT/'.env.example')
    values['AGENT_SERVICE_TOKEN']=secrets.token_urlsafe(32)
    values['POSTGRES_PASSWORD']=secrets.token_urlsafe(32)
    values['OPENAI_API_KEY']=read_env(args.reference_env).get('OPENAI_API_KEY','') if args.reference_env else os.getenv('OPENAI_API_KEY','')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write('# Phonease local settings. Do not commit.\n')
        for key,value in values.items(): stream.write(key+'='+value+'\n')
    print('Created private .env; OpenAI '+('configured.' if values['OPENAI_API_KEY'] else 'not configured (local rules available).'))

if __name__=='__main__': main()
