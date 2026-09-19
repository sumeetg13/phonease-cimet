"""Single-writer, script-driven Energy recovery supervisor. Synthetic data only."""
import copy
import json
import math
import re
import threading
import time
import uuid
from .signals import detect, validate_analysis

from .script_registry import SCRIPTS, FIELDS, SECTIONS, line, pick
TERMINAL = {'completed', 'declined', 'suppressed', 'human', 'callback', 'ended'}
CONFIRM_CONFIDENCE = 0.75  # Below this, a model-read affirmation/rejection is treated as unclear, not silently accepted.

# Local (offline) synonym vocabulary for yes/no. Split on comma/"and" so stacked casual
# replies ("yeah, sure") still match, but every resulting clause must be a known phrase —
# this keeps it conservative instead of doing keyword search over the whole sentence.
YES_TERMS = {'yes','yeah','yeh','yea','yep','yup','sure','okay','ok','alright','all right',
    'correct','definitely','absolutely','certainly','totally','affirmative','fine',
    'that is correct',"that's correct",'i agree','i consent','please continue','go ahead',
    'of course','sounds good',"that's fine",'no problem','why not','that works',
    'works for me','fine by me','yes please','sure thing'}
NO_TERMS = {'no','nope','nah','negative','incorrect','wrong',
    "i don't agree",'i do not agree','not really','not at all','no way','i disagree'}
# Live call notes, written as the call happens: outcomes and topics, never verbatim caller
# speech, so a note is safe to keep before consent covers transcript storage.
SIGNAL_NOTES = {
    'sensitive': 'Raised hardship, a billing dispute or a vulnerability concern.',
    'distress': 'Sounded distressed during the call.',
    'privacy': 'Asked where their details came from.',
    'accessibility': 'Asked for accessibility support with hearing or pace.',
    'language': 'Asked to continue in another language.',
    'busy': 'Said this was not a good time to talk.',
    'payment': 'Offered payment details; these are never collected on this call.',
    'off_script': 'Asked for a plan recommendation or advice.',
    'anger': 'Sounded frustrated with the process.',
    'confusion': 'Did not understand a question; it was rephrased.',
    'technical': 'Reported a problem with the line.',
    'human': 'Asked to speak to a person.',
    'dnc': 'Asked not to be contacted again.',
    'decline': 'Declined to continue.',
}
OUTCOME_NOTES = {
    'completed': 'Details submitted for further processing.',
    'declined': 'Caller declined; nothing was submitted.',
    'suppressed': 'Added to the do-not-contact list; nothing was submitted.',
    'callback': 'Call ended for a call back later; nothing was submitted.',
    'ended': 'Call ended; nothing was submitted.',
}
NAME_PATTERN = re.compile(r"[A-Za-z]+(?:[ '\-][A-Za-z]+)*")
NAME_PREFIXES = ("my name is ","i am ","i'm ","this is ","it's ","it is ","call me ","name's ")

def now():
    return round(time.time(), 3)

def norm(text):
    return re.sub(r'\s+', ' ', text.lower().replace('’', "'")).strip()

def polarity_match(text, terms):
    t = norm(text).strip(' .!')
    if not t: return False
    clauses = [c.strip(' .!,') for c in re.split(r',|\band\b', t)]
    clauses = [c for c in clauses if c]
    return bool(clauses) and all(c in terms for c in clauses)

def is_yes(text): return polarity_match(text, YES_TERMS)
def is_no(text): return polarity_match(text, NO_TERMS)

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
        if is_yes(t): return True
        if is_no(t): return False
    if typ == 'text':
        for prefix in NAME_PREFIXES:
            if t.startswith(prefix):
                t = t[len(prefix):]
                break
        candidate = ' '.join(w.capitalize() for w in t.split())
        if candidate and valid(field, candidate): return candidate
    return None

def valid(field, value):
    spec = FIELDS[field]
    if spec['type'] == 'postcode': return isinstance(value, str) and bool(re.fullmatch(spec['validation']['pattern'], value))
    if spec['type'] == 'boolean': return type(value) is bool
    if spec['type'] == 'text':
        return (isinstance(value, str) and 1<=len(value)<=60 and bool(NAME_PATTERN.fullmatch(value))
            and value.lower() not in YES_TERMS and value.lower() not in NO_TERMS)
    return value in spec['choices'] if isinstance(value, str) else False

def display(value):
    return ('yes' if value else 'no') if type(value) is bool else str(value)

def transcript(s):
    # What was actually said, in order. Caller lines are already redacted and sanitized.
    return [{'role': e['kind'], 'text': e['content'], 'turn': e['turn'], 'at': e['at']}
            for e in s['events'] if e['kind'] in ('assistant', 'caller')]

def applicable(s, key):
    # A conditional field (e.g. bill amount vs household estimate) only becomes part
    # of the journey once its trigger field is answered a specific way.
    dep = FIELDS[key].get('depends_on')
    if not dep: return True
    seen = s['fields'].get(dep['field'])
    return seen is not None and seen['value'] == dep['equals']

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
        assert s['consent'] and all(k in s['fields'] and valid(k, s['fields'][k]['value'])
            for k in FIELDS if applicable(s, k))
        # The receipt carries the call record with the answers: transcript and notes, not audio.
        payload = {'schema_version': SCRIPTS['version'], 'lead_id': s['lead_id'], 'vertical': 'energy',
                   'consent': True, 'fields': {k:v['value'] for k,v in s['fields'].items()},
                   'notes': copy.deepcopy(s.get('notes', [])), 'transcript': transcript(s)}
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
                 'mode':'model-assisted' if self.model else 'deterministic-demo', 'receipt':None, 'handoff':None, 'analysis':None, 'script_version':SCRIPTS['version'], 'sections_introduced':[],
                 'notes':[], 'noted_signals':[], 'summary':None}
            for k,v in (seed or {}).items():
                if k not in FIELDS or not valid(k,v): raise ValueError('Invalid seed field')
                s['fields'][k] = {'value':v, 'source':'synthetic-lead', 'confirmed':True, 'turn':0}
            self.event(s, 'gate', 'Synthetic lead and local DNC check passed; external DNC stub.')
            self.note(s, 'call', 'Recovery call opened on a synthetic lead.')
            for k, v in s['fields'].items():
                self.note(s, 'detail', FIELDS[k]['label']+': '+display(v['value'])+' (carried over from the earlier journey)')
            self.say(s, pick(SCRIPTS['opening']))
            self.store.save(s)
            return s

    def note(self, s, kind, text):
        s.setdefault('notes', []).append({'at':now(), 'turn':s['turn'], 'kind':kind, 'text':text})

    def finalize(self, s):
        # The record the operator reads after the call: what was said, noted and submitted.
        s['summary'] = {'session_id':s['id'], 'lead_id':s['lead_id'], 'outcome':s['state'],
            'ended_at':now(), 'consent':s['consent'], 'script_version':s.get('script_version'),
            'fields':[{'key':k, 'label':FIELDS[k]['label'], 'value':display(s['fields'][k]['value'])}
                      for k in FIELDS if k in s['fields']],   # Script order, with the spoken label.
            'handoff_reason':(s.get('handoff') or {}).get('reason'),
            'notes':copy.deepcopy(s.get('notes', [])), 'transcript':transcript(s),
            'receipt':copy.deepcopy(s.get('receipt'))}

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
        return next((k for k in FIELDS if k not in s['fields'] and applicable(s, k)), None)

    def reconcile(self, s):
        # A changed answer can make an already-collected conditional field stale
        # (e.g. a bill amount collected while has_bill=true, after it flips to false).
        changed = True
        while changed:
            changed = False
            for k in list(s['fields']):
                if not applicable(s, k):
                    del s['fields'][k]
                    changed = True

    def ask_next(self, s):
        f = self.next_field(s)
        if f:
            s['state']='collecting'
            section=SECTIONS[FIELDS[f]['section']]
            introductions=s.setdefault('sections_introduced',[])
            prefix=''
            if section['id'] not in introductions:
                if not introductions and s['fields']: prefix=line('resume')+' '
                prefix+=pick(section['intro'])+' '
                introductions.append(section['id'])
            self.say(s, prefix+FIELDS[f]['question'])
        else:
            s['state']='review'
            summary = '; '.join(FIELDS[k]['label']+': '+display(v['value']) for k,v in s['fields'].items())
            self.say(s, line('review',summary=summary))

    def close(self, s, state, message, note=None):
        s['state']=state
        s['pending']=None
        note = note or OUTCOME_NOTES.get(state)
        if note: self.note(s,'outcome',note)
        self.say(s,message)
        self.finalize(s)

    def handover(self, s, reason):
        if s['state']=='handoff_pending':
            return self.say(s,line('handoff_pending'))
        s['state']='handoff_pending'
        self.note(s,'escalation','Handover to an energy specialist: '+reason.replace('_',' ')+'.')
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
            noted = s.setdefault('noted_signals', [])
            for item in detected:
                if item['label'] in SIGNAL_NOTES and item['label'] not in noted:
                    noted.append(item['label'])
                    self.note(s, 'concern', SIGNAL_NOTES[item['label']])
            if s['consent']: self.event(s,'caller',safe_text)
            self._advance(s,text,[item['label'] for item in detected],confidence,result,status)
            self.store.save(s)
            return s

    def _advance(self,s,text,detected,confidence,result=None,model_status=None):
        t=norm(text)
        if 'dnc' in detected:
            self.store.suppress(s['lead_id'])
            return self.close(s,'suppressed',line('suppressed'))
        if 'decline' in detected or (s['state']=='consent' and is_no(t)):
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
            if is_yes(t):
                s['consent']=True
                self.event(s,'consent','Explicit affirmative consent; transcript storage enabled; audio recording disabled.')
                self.note(s,'consent','Consent given to continue and store the transcript. No audio is recorded.')
                return self.ask_next(s)
            return self.repair(s,'consent',line('consent_clarification'))
        if s['state']=='confirming':
            pending=s['pending']; f=pending['field']
            if is_yes(t) or self.affirmed(result,'yes'):
                s['fields'][f]={'value':pending['value'],'confirmed':True,'source':pending['source'],'turn':s['turn']}
                s['pending']=None
                self.note(s,'detail',FIELDS[f]['label']+': '+display(pending['value'])+' (confirmed by the caller)')
                self.reconcile(s)
                return self.ask_next(s)
            if is_no(t) or self.affirmed(result,'no'):
                s['pending']=None; s['state']='collecting'
                self.note(s,'detail',FIELDS[f]['label']+': the read-back was wrong; asked again.')
                return self.repair(s,f,line('correction',question=FIELDS[f]['clarification']))
            return self.repair(s,f,line('confirm_clarification',question=self.current_question(s)))
        if s['state']=='review':
            if is_yes(t) or self.affirmed(result,'yes'):
                try: s['receipt']=self.store.submit(s)
                except Exception:
                    return self.handover(s,'submission_failure')
                return self.close(s,'completed',line('completed'),
                    'Details submitted for further processing. Receipt '+s['receipt']['id']+' ('+s['receipt']['adapter']+').')
            changes=[k for k in FIELDS if k in t or FIELDS[k]['label'].lower() in t]
            if len(changes)==1:
                self.note(s,'detail',FIELDS[changes[0]]['label']+': caller asked to change this before submitting.')
                del s['fields'][changes[0]]
                self.reconcile(s)
                return self.ask_next(s)
            if is_no(t) or self.affirmed(result,'no'): return self.close(s,'declined',line('submit_declined'))
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

    def affirmed(self,result,answer):
        # Only the model reads paraphrased yes/no; the regex is not the only path.
        confirmation = (result or {}).get('confirmation')
        return bool(confirmation) and confirmation['answer']==answer and confirmation['confidence']>=CONFIRM_CONFIDENCE

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
            self.note(s,'outcome','Energy specialist accepted the call; the AI stopped. Nothing was submitted.')
            s['message']='Human accepted the context. AI conversation stopped.'
            self.finalize(s)
            self.store.save(s); return s

    def unavailable(self,sid):
        with self.lock:
            s=self.store.get(sid)
            if s['state'] in TERMINAL: return s
            if s['state']!='handoff_pending': raise ValueError('No pending handoff')
            s['handoff']['status']='unavailable'; s['revision']+=1
            self.close(s,'callback','No specialist was available; a call back was offered.')
            self.store.save(s); return s
