"""Intent/safety taxonomy and conservative local fallback; not a trained classifier."""
import re

LABELS = ['dnc', 'decline', 'human', 'payment', 'sensitive', 'busy', 'off_script',
          'anger', 'confusion', 'distress', 'privacy', 'accessibility', 'language',
          'technical', 'low_confidence']
SENTIMENTS = ['positive', 'neutral', 'negative', 'mixed', 'unknown']
SEVERITIES = ['low', 'medium', 'high']

def normalize(text):
    return re.sub(r'\s+', ' ', text.lower().replace('’', "'")).strip()

# Examples make the offline demo useful. Semantic paraphrases require the model.
RULES = {
    'dnc': r"stop (calling|contacting)|do not (call|contact)|don't (call|contact)|remove me|take me off|never call|unsubscribe|delete my (number|contact)|leave me alone",
    'decline': r"no thanks|no thank you|not interested|don't want to (continue|proceed)|do not want to (continue|proceed)|end (the|this) call|hang up|withdraw.*consent|don't consent|do not consent|don't record|do not record",
    'human': r"\b(human|real person|someone else|supervisor)\b|(?:speak|talk) (?:to|with).*(?:person|agent|representative)|put me through|(?:real|actual) (?:employee|operator)|not (?:a |this )?(?:bot|robot)|someone who (?:can|actually)",
    'payment': r'\b(card number|credit card|debit card|cvv|cvc|bank account|payment details|pay by card)\b|(?:\d[ -]?){12,19}',
    'sensitive': r"\b(dispute|hardship|vulnerable|ombudsman|life support|overcharged|fraud|scam)\b|can't afford|cannot afford|medical equipment|domestic violence|financial abuse|charged (?:me )?twice|formal complaint",
    'busy': r"\bbusy\b|call (me )?(back|later)|another time|can't talk|cannot talk|in a meeting|driving right now",
    'off_script': r"\b(recommend|advice|cheapest|best plan|guarantee|which plan|should i choose)\b",
    'anger': r"\b(angry|frustrated|frustrating|ridiculous|useless|furious|damn|shit|fuck|annoyed|annoying)\b|already told|second call|third call|keep calling|going (?:round|around) in circles|wasting my time|fed up|said (?:this|that|it) (?:before|already)",
    'confusion': r"(?:don't|do not|can't|cannot) understand|(?:i'm|i am) confused|what do you mean|makes no sense|lost me|explain (?:that|it) again",
    'distress': r"\b(panicking|overwhelmed|terrified|crying)\b|can't cope|cannot cope|(?:i'm|i am) scared",
    'privacy': r"where did you get my (?:number|details)|how did you get my (?:number|details)|who (?:gave|sold) you my|data (?:protection|privacy)|privacy concern|why (?:are you|do you need to) recording|why (?:do you need|are you asking for) (?:my|this)",
    'accessibility': r"hard of hearing|hearing (?:loss|impaired)|can't hear|cannot hear|speak (?:more )?slowly|talk (?:more )?slowly|need (?:an? )?(?:interpreter|accessible)|screen reader",
    'language': r"(?:don't|do not|can't|cannot) (?:speak|understand) english|(?:speak|talk) (?:in )?(?:hindi|punjabi|mandarin|spanish|arabic)|another language",
    'technical': r"line (?:is )?(?:breaking|crackling)|(?:you(?:'re| are)|audio (?:is )?) (?:breaking|cutting) up|connection (?:is )?bad|bad connection|can't hear you|cannot hear you"
}

def detect(text):
    t = normalize(text)
    # Evaluate separate clauses so "not angry, but get me a person" retains its request.
    clauses = re.split(r'[.!?;]|\bbut\b|\bhowever\b', t)
    found = []
    for label, pattern in RULES.items():
        for clause in clauses:
            if label == 'human' and re.search(r"(?:don't|do not) (?:need|want)|no need (?:for|to)|not asking for", clause):
                continue
            if label == 'anger' and re.search(r"(?:not|never) (?:angry|frustrated|annoyed|furious)|(?:was|were) (?:angry|frustrated)|old (?:retailer|provider)", clause):
                continue
            if label == 'busy' and re.search(r"(?:not|never) busy|(?:don't|do not) call (?:me )?(?:back|later)", clause):
                continue
            if label == 'dnc' and re.search(r"(?:don't|do not) stop (?:calling|contacting)", clause):
                continue
            match = re.search(pattern, clause)
            if match:
                high = label == 'anger' and bool(re.search(r'furious|fuck|shit|already told|second call|third call|fed up', clause))
                found.append({'label':label, 'severity':'high' if high else 'medium',
                              'evidence':match.group(0), 'source':'rules'})
                break
    return found

def validate_analysis(result, text):
    """Do not trust provider JSON or unconstrained model-generated explanations."""
    if not isinstance(result, dict) or set(result) != {'value','signals','sentiment','confirmation'}:
        raise ValueError('Invalid analysis shape')
    if result['value'] is not None and (not isinstance(result['value'], str) or len(result['value']) > 100):
        raise ValueError('Invalid candidate')
    if result['sentiment'] not in SENTIMENTS or not isinstance(result['signals'],list) or len(result['signals'])>8:
        raise ValueError('Invalid analysis labels')
    confirmation = result['confirmation']
    if confirmation is not None:
        if not isinstance(confirmation, dict) or set(confirmation) != {'answer','confidence'}:
            raise ValueError('Invalid confirmation shape')
        if confirmation['answer'] not in ('yes','no','unclear'):
            raise ValueError('Invalid confirmation answer')
        if type(confirmation['confidence']) not in (int,float) or not 0<=confirmation['confidence']<=1:
            raise ValueError('Invalid confirmation confidence')
    seen = set()
    for signal in result['signals']:
        if not isinstance(signal,dict) or set(signal) != {'label','severity','evidence'}:
            raise ValueError('Invalid signal shape')
        if signal['label'] not in LABELS or signal['label'] in seen or signal['severity'] not in SEVERITIES:
            raise ValueError('Invalid signal label')
        evidence = signal['evidence']
        if not isinstance(evidence,str) or not evidence.strip() or len(evidence)>200 or normalize(evidence) not in normalize(text):
            raise ValueError('Signal evidence must quote the current turn')
        seen.add(signal['label'])
    return result
