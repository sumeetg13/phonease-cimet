"""Versioned, shared contract for spoken scripts, capture and operator guidance."""
import json
import random
import re
from pathlib import Path
from string import Formatter

def pick(value):
    """Choose one spoken variant. Same meaning, different phrasing; not model-generated."""
    return random.choice(value) if isinstance(value, list) else value

def lines(value, what):
    # Accept a single string or a list of same-meaning variants; normalize to a non-empty list.
    variants = [value] if isinstance(value, str) else value
    if not isinstance(variants, list) or not variants or any(not isinstance(v, str) or not v.strip() for v in variants):
        raise ValueError(what+' must be a non-empty string or list of non-empty strings')
    return variants

def validate_registry(registry):
    if not registry.get('version') or not registry.get('opening'): raise ValueError('Version/opening required')
    registry['opening'] = lines(registry['opening'], 'opening')
    sections = registry['sections']; fields = registry['fields']
    section_ids = [s['id'] for s in sections]
    if len(section_ids)!=len(set(section_ids)): raise ValueError('Duplicate section')
    keys = [f['key'] for f in fields]
    if len(keys)!=len(set(keys)): raise ValueError('Duplicate field')
    for section in sections:
        if not section.get('intro') or not section.get('purpose'): raise ValueError('Incomplete section script')
        section['intro'] = lines(section['intro'], 'section intro')
    for f in fields:
        if f['section'] not in section_ids: raise ValueError('Unknown section')
        if f['type'] not in ('postcode','enum','boolean','text'): raise ValueError('Unsupported field type')
        if f.get('required') is not True: raise ValueError('This demo supports required fields only')
        if type(f.get('max_failed_attempts')) is not int or not 1<=f['max_failed_attempts']<=3: raise ValueError('Invalid repair budget')
        for key in ('label','question','clarification','confirmation','purpose','validation'):
            if not f.get(key): raise ValueError('Incomplete field script: '+key)
        placeholders={key for _,key,_,_ in Formatter().parse(f['confirmation']) if key}
        if placeholders!={'value'}: raise ValueError('Confirmation must contain only {value}')
        if f['type']=='postcode': re.compile(f['validation']['pattern'])
        if f['type']=='enum' and not f.get('choices'): raise ValueError('Enum requires choices')
        allowed = f.get('choices',[]) if f['type']=='enum' else ['true','false'] if f['type']=='boolean' else list(f.get('aliases',{}))
        if any(key not in allowed for key in f.get('aliases',{})): raise ValueError('Invalid alias value')
        dep = f.get('depends_on')
        if dep is not None:
            if set(dep) != {'field','equals'} or dep['field'] not in keys or dep['field']==f['key'] or not isinstance(dep['equals'],bool):
                raise ValueError('Invalid depends_on')
    return registry

SCRIPTS=validate_registry(json.loads(Path(__file__).with_name('scripts.json').read_text()))
FIELDS={f['key']:f for f in SCRIPTS['fields']}
SECTIONS={s['id']:s for s in SCRIPTS['sections']}

def line(key, **values):
    return SCRIPTS['messages'][key].format(**values)
