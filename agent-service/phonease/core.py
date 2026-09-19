"""Single-writer, script-driven Energy recovery supervisor. Synthetic data only."""
import copy
import json
import math
import re
import threading
import time
import uuid
from .signals import detect, validate_analysis

from .script_registry import SCRIPTS, FIELDS, SECTIONS, line
TERMINAL = {'completed', 'declined', 'suppressed', 'human', 'callback', 'ended'}
YES = re.compile(r'^(yes|yeah|yep|correct|that is correct|that\'s correct|sure|okay|ok|i agree|i consent|please continue|go ahead)[.! ,]*$', re.I)
NO = re.compile(r'^(no|nope|nah|incorrect|wrong)[.! ,]*$', re.I)

def now():
    return round(time.time(), 3)

def norm(text):
    return re.sub(r'\s+', ' ', text.lower().replace('’', "'")).strip()

def signals(text):
    return [item['label'] for item in detect(text)]

def sanitize(text):
    # Discard entire payment utterance; digit masking alone misses spoken card numbers.
    if 'payment' in signals(text):
        return '[payment-related utterance withheld]'
    return re.sub(r'(?:\d[ -]?){8,}', '[long number withheld]', text)[:1200]

def parse_value(field, text):
    t = norm(text).rstrip('.!')
    spec = FIELDS[field]
    typ = spec['type']
    for value, aliases in spec.get('aliases',{}).items():
        if t in aliases:
            return value=='true' if typ=='boolean' else value
    if typ == 'postcode':
        words = {'zero':'0','oh':'0','one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9'}
        spoken = ''.join(words.get(w, '') for w in t.split())
        nums = re.findall(r'(?<!\d)\d{4}(?!\d)', t)
        if len(nums) == 1: return nums[0]
        if len(spoken) == 4: return spoken
    if typ == 'enum':
        combination=spec.get('combination')
        if combination and all(re.search(r'\b'+re.escape(v)+r'\b',t) for v in combination['members']) and not re.search(r"\b(no|not|don't)\b",t):
            return combination['value']
        found = [x for x in FIELDS[field]['choices'] if re.search(r'\b'+x+r'\b', t)]
        if len(found) == 1 and not re.search(r"\b(no|not|don't|do not)\b", t): return found[0]
    if typ == 'boolean':
        if YES.fullmatch(t): return True
        if NO.fullmatch(t): return False
    return None

def valid(field, value):
    spec = FIELDS[field]
    if spec['type'] == 'postcode': return isinstance(value, str) and bool(re.fullmatch(spec['validation']['pattern'], value))
    if spec['type'] == 'boolean': return type(value) is bool
    return value in spec['choices'] if isinstance(value, str) else False

def display(value):
    return ('yes' if value else 'no') if type(value) is bool else str(value)

class Store:
    """Request-local working state. Spring Boot owns all durable PostgreSQL writes."""
    def __init__(self, path=None):
        self.sessions = {}
        self.suppression = set()
        self.receipts = {}

    def get(self, sid):
        if sid not in self.sessions: raise KeyError('Unknown session')
        return copy.deepcopy(self.sessions[sid])

    def save(self, s):
        self.sessions[s['id']] = copy.deepcopy(s)

    def suppressed(self, lead):
        return lead in self.suppression

    def suppress(self, lead):
        self.suppression.add(lead)

    def submit(self, s):
        # Local mock journey-completion adapter. Lead ID is the demo journey's idempotency key.
        assert s['consent'] and all(k in s['fields'] and valid(k, s['fields'][k]['value']) for k in FIELDS)
        payload = {'schema_version': SCRIPTS['version'], 'lead_id': s['lead_id'], 'vertical': 'energy',
                   'consent': True, 'fields': {k:v['value'] for k,v in s['fields'].items()}}
        receipt = 'mock-'+uuid.uuid4().hex[:12]
        self.receipts.setdefault(s['lead_id'], {'id':receipt, 'adapter':'local-mock', 'payload':payload})
        return copy.deepcopy(self.receipts[s['lead_id']])

class Supervisor:
    def __init__(self, store=None, model=None):
        self.store = store or Store()
        self.model = model
        self.lock = threading.RLock()  # Single process only. Production: per-call actor + transactional event store.

    def start(self, lead=None, seed=None):
        with self.lock:
            lead = lead or 'synthetic-'+uuid.uuid4().hex[:8]
            if not re.fullmatch(r'synthetic-[a-zA-Z0-9_-]{1,64}', lead): raise ValueError('Only synthetic-* lead IDs allowed')
            if self.store.suppressed(lead): raise ValueError('DNC gate: lead suppressed')
            s = {'id':uuid.uuid4().hex, 'lead_id':lead, 'state':'consent', 'consent':False,
                 'fields':{}, 'pending':None, 'failures':{}, 'events':[], 'signals':[], 'seen':{},
                 'turn':0, 'created_at':now(), 'revision':0, 'anger_count':0,
                 'mode':'model-assisted' if self.model else 'deterministic-demo', 'receipt':None, 'handoff':None, 'analysis':None, 'script_version':SCRIPTS['version'], 'sections_introduced':[]}
            for k,v in (seed or {}).items():
                if k not in FIELDS or not valid(k,v): raise ValueError('Invalid seed field')
                s['fields'][k] = {'value':v, 'source':'synthetic-lead', 'confirmed':True, 'turn':0}
            self.event(s, 'gate', 'Synthetic lead and local DNC check passed; external DNC stub.')
            self.say(s, SCRIPTS['opening'])
            self.store.save(s)
            return s

    def event(self, s, kind, content):
        s['events'].append({'at':now(), 'turn':s['turn'], 'kind':kind, 'content':content})

    def say(self, s, message):
        s['message'] = message
        f=(s['pending'] or {}).get('field') or self.next_field(s)
        active_field=FIELDS.get(f) if s['state'] in ('collecting','confirming') else None
        s['active_script']={'version':s.get('script_version'), 'stage':s['state'],
            'section':copy.deepcopy(SECTIONS[active_field['section']]) if active_field else None,
            'field':copy.deepcopy(active_field), 'spoken_line':message}
        self.event(s, 'assistant', message)

    def next_field(self, s):
        return next((k for k in FIELDS if k not in s['fields']), None)

    def ask_next(self, s):
        f = self.next_field(s)
        if f:
            s['state']='collecting'
            section=SECTIONS[FIELDS[f]['section']]
            introductions=s.setdefault('sections_introduced',[])
            prefix=''
            if section['id'] not in introductions:
                if not introductions and s['fields']: prefix=line('resume')+' '
                prefix+=section['intro']+' '
                introductions.append(section['id'])
            self.say(s, prefix+FIELDS[f]['question'])
        else:
            s['state']='review'
            summary = '; '.join(FIELDS[k]['label']+': '+display(v['value']) for k,v in s['fields'].items())
            self.say(s, line('review',summary=summary))

    def close(self, s, state, message):
        s['state']=state
        s['pending']=None
        self.say(s,message)

    def handover(self, s, reason):
        if s['state']=='handoff_pending':
            return self.say(s,line('handoff_pending'))
        s['state']='handoff_pending'
        s['handoff']={'reason':reason, 'queue':'energy-specialist', 'status':'awaiting_acceptance',
            'lead_id':s['lead_id'], 'session_id':s['id'], 'consent':s['consent'],
            'confirmed_fields':copy.deepcopy(s['fields']), 'unconfirmed':copy.deepcopy(s['pending']),
            'next_field':self.next_field(s), 'failures':dict(s['failures']),
            'signals':copy.deepcopy(s['signals']), 'recent_events':copy.deepcopy(s['events'][-12:]),
            'script_version':s.get('script_version'), 'active_script':copy.deepcopy(s.get('active_script')), 'created_at':now()}
        self.say(s, line('handoff'))

    def repair(self, s, key, message):
        s['failures'][key]=s['failures'].get(key,0)+1
        if s['failures'][key]>=FIELDS.get(key,{}).get('max_failed_attempts',2):
            self.handover(s, 'two_failed_attempts:'+key)
        else:
            self.say(s, message)

    def turn(self, sid, text, event_id, confidence=None, revision=None):
        if not isinstance(text,str) or len(text)>1200: raise ValueError('Turn must be text, max 1200 characters')
        if not isinstance(event_id,str) or not 1 <= len(event_id) <= 128: raise ValueError('event_id required')
        if confidence is not None and (type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1): raise ValueError('confidence must be 0..1 or null')
        with self.lock:
            s=self.store.get(sid)
            if event_id in s['seen']: return s
            if revision is not None and revision != s['revision']: raise ValueError('Stale turn: refresh session')
            if s['state'] in TERMINAL: return s
            if s.get('script_version') != SCRIPTS['version']: raise ValueError('Script version changed. Start a new synthetic call.')
            s['turn']+=1; s['revision']+=1
            s['seen'][event_id]=s['revision']
            detected = detect(text)
            result = None
            status = 'not_configured' if not self.model else 'consent_required'
            preempt = {'dnc','decline','human','payment','sensitive','busy','off_script','distress','privacy','accessibility','language'}
            # Rules may preempt the model. Never transmit a known payment utterance.
            if self.model and s['consent']:
                if any(item['label'] in preempt for item in detected):
                    status = 'rules_preempted'
                elif not text.strip():
                    status = 'empty_turn'
                else:
                    try:
                        field = self.next_field(s) if s['state']=='collecting' else None
                        context = {'stage':s['state'], 'question':s['message'],
                                   'recent_turns':[{'role':e['kind'],'text':e['content']}
                                       for e in s['events'] if e['kind'] in ('assistant','caller')][-6:]}
                        result = validate_analysis(self.model.analyze(field, sanitize(text), context), sanitize(text))
                        status = 'analyzed'
                        # Merge independent signals; a model cannot remove a rule's decision.
                        for item in result['signals']:
                            existing = next((x for x in detected if x['label']==item['label']),None)
                            if existing:
                                if item['severity']=='high': existing['severity']='high'
                            else: detected.append(dict(item,source='model'))
                    except Exception:
                        status = 'unavailable'
                        self.event(s,'model','Signal model unavailable or invalid; no proposal applied.')
            s['analysis'] = {'source':'model' if result else 'rules',
                'model_status':status, 'sentiment':result['sentiment'] if result else 'unknown',
                'signals':copy.deepcopy(detected), 'turn':s['turn']}
            # Payment detection may be semantic: redact before ANY persistence or packet copy.
            payment = any(x['label']=='payment' for x in detected)
            safe_text = '[payment-related utterance withheld]' if payment else sanitize(text)
            for item in detected:
                s['signals'].append({'signal':item['label'],'severity':item['severity'],
                    'evidence':'[withheld]' if payment else sanitize(item['evidence']),
                    'turn':s['turn'],'source':item['source']})
            if payment:
                for item in s['analysis']['signals']: item['evidence']='[withheld]'
            if s['consent']: self.event(s,'caller',safe_text)
            self._advance(s,text,[item['label'] for item in detected],confidence,result,status)
            self.store.save(s)
            return s

    def _advance(self,s,text,detected,confidence,result=None,model_status=None):
        t=norm(text)
        if 'dnc' in detected:
            self.store.suppress(s['lead_id'])
            return self.close(s,'suppressed',line('suppressed'))
        if 'decline' in detected or (s['state']=='consent' and NO.fullmatch(t)):
            return self.close(s,'declined',line('declined'))
        if 'human' in detected: return self.handover(s,'explicit_human_request')
        if 'payment' in detected: return self.handover(s,'payment_boundary')
        if 'sensitive' in detected: return self.handover(s,'sensitive_or_vulnerable')
        if 'busy' in detected:
            return self.close(s,'callback',line('busy'))
        if 'off_script' in detected: return self.handover(s,'advice_or_off_script')
        for signal in ('distress','privacy','accessibility','language'):
            if signal in detected: return self.handover(s,signal)
        if s['state']=='handoff_pending':
            return self.say(s,line('handoff_pending'))
        if 'anger' in detected:
            s['anger_count'] = len({e['turn'] for e in s['signals']
                if e['signal']=='anger' and e['turn']>=s['turn']-2})
            severe = any(e['signal']=='anger' and e.get('severity')=='high'
                and e['turn']==s['turn'] for e in s['signals'])
            if s['anger_count']>=2 or severe:
                return self.handover(s,'frustration')
            return self.say(s,line('frustration',question=self.current_question(s)))
        if s['state']=='handoff_pending':
            return self.say(s,line('handoff_pending'))
        key = (s['pending'] or {}).get('field') or self.next_field(s) or s['state']
        if model_status=='unavailable':
            return self.handover(s,'model_unavailable')
        if any(x in detected for x in ('confusion','low_confidence','technical')):
            return self.repair(s,key,line('confusion',question=self.current_question(s)))
        if not t or (confidence is not None and confidence<0.65):
            return self.repair(s,key,line('misheard',question=self.current_question(s)))
        if s['state']=='consent':
            if YES.fullmatch(t):
                s['consent']=True
                self.event(s,'consent','Explicit affirmative consent; transcript storage enabled; audio recording disabled.')
                return self.ask_next(s)
            return self.repair(s,'consent',line('consent_clarification'))
        if s['state']=='confirming':
            pending=s['pending']; f=pending['field']
            if YES.fullmatch(t):
                s['fields'][f]={'value':pending['value'],'confirmed':True,'source':pending['source'],'turn':s['turn']}
                s['pending']=None
                return self.ask_next(s)
            if NO.fullmatch(t):
                s['pending']=None; s['state']='collecting'
                return self.repair(s,f,line('correction',question=FIELDS[f]['clarification']))
            return self.repair(s,f,line('confirm_clarification',question=self.current_question(s)))
        if s['state']=='review':
            if YES.fullmatch(t):
                try: s['receipt']=self.store.submit(s)
                except Exception:
                    return self.handover(s,'submission_failure')
                return self.close(s,'completed',line('completed'))
            changes=[k for k in FIELDS if k in t or FIELDS[k]['label'].lower() in t]
            if len(changes)==1:
                del s['fields'][changes[0]]
                return self.ask_next(s)
            if NO.fullmatch(t): return self.close(s,'declined',line('submit_declined'))
            return self.repair(s,'review',line('review_clarification',field_names=', '.join(FIELDS)))
        f=self.next_field(s)
        value=parse_value(f,text); source='rules'
        if result and value is None:
            candidate=result['value']
            if FIELDS[f]['type']=='boolean' and candidate in ('true','false'): candidate=candidate=='true'
            if candidate is not None and valid(f,candidate): value=candidate; source='model-proposal'
        if value is None: return self.repair(s,f,line('capture_clarification',question=FIELDS[f]['clarification']))
        s['pending']={'field':f,'value':value,'source':source}
        s['state']='confirming'
        self.say(s,FIELDS[f]['confirmation'].format(value=display(value)))

    def current_question(self,s):
        if s['state']=='consent': return line('consent_question')
        if s['pending']: return FIELDS[s['pending']['field']]['confirmation'].format(value=display(s['pending']['value']))
        f=self.next_field(s)
        return FIELDS[f]['clarification'] if f else line('submit_question')

    def accept(self,sid,agent):
        with self.lock:
            s=self.store.get(sid)
            if s['state']=='human': return s
            if s['state']!='handoff_pending': raise ValueError('No pending handoff')
            s['handoff']['status']='accepted'; s['handoff']['agent']=agent[:60]
            s['handoff']['accepted_at']=now(); s['state']='human'; s['revision']+=1
            self.event(s,'handoff','Human accepted; AI no longer owns the conversation.')
            s['message']='Human accepted the context. AI conversation stopped.'
            self.store.save(s); return s

    def unavailable(self,sid):
        with self.lock:
            s=self.store.get(sid)
            if s['state'] in TERMINAL: return s
            if s['state']!='handoff_pending': raise ValueError('No pending handoff')
            s['handoff']['status']='unavailable'; s['revision']+=1
            self.close(s,'callback',line('unavailable'))
            self.store.save(s); return s
