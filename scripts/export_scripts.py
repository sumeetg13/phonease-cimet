#!/usr/bin/env python3
"""Generate the human-readable script book from the runtime registry."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
r=json.loads((root/'agent-service/phonease/scripts.json').read_text())
lines=['# Energy recovery: shared human and AI script book','',
       'Generated from `agent-service/phonease/scripts.json`. Edit the registry, then run `./scripts/export_scripts.py`.', '',
       '**Version:** '+r['version']+' · **Status:** draft assumptions','',r['notice'],'',
       'The recording, official field list and sandbox schema have not been supplied. These scripts are not represented as derived from that missing material.', '',
       '## Opening and consent','',
       'One variant is chosen at random per call; all convey the same disclosure and consent request.','']
opening=r['opening'] if isinstance(r['opening'],list) else [r['opening']]
lines+=['- '+v for v in opening]+['',
       'Do not collect journey fields before affirmative consent. Existing confirmed values are retained; only missing fields are asked. A section introduction is read once when entering that section.', '']
for section in r['sections']:
    intro=section['intro'] if isinstance(section['intro'],list) else [section['intro']]
    lines+=['## '+section['title'],'', '**Section intent:** '+section['purpose'],'', '**Section script variants:**','']
    lines+=['- '+v for v in intro]+['']
    for f in [f for f in r['fields'] if f['section']==section['id']]:
        lines+=['### '+f['label']+' (`'+f['key']+'`)','',
          '- **Collect:** '+f['purpose'], '- **Ask:** '+f['question'],
          '- **Clarify:** '+f['clarification'], '- **Read back:** '+f['confirmation'],
          '- **Validate:** '+f['validation']['description'],
          '- **Failure limit:** '+str(f['max_failed_attempts'])+' failed attempts, then human handover.']
        if f.get('aliases'):
            lines+=['- **Examples of accepted phrasing:** '+ '; '.join(' / '.join(v)+' → '+k for k,v in f['aliases'].items())]
        if f.get('depends_on'):
            lines+=['- **Asked only if:** `'+f['depends_on']['field']+'` is '+str(f['depends_on']['equals']).lower()]
        lines+=['']
lines+=['## Final review','',r['messages']['review'],'',
        '`{summary}` is generated only from validated, confirmed fields. A final explicit yes permits mock submission. A named correction reopens that field. No plan purchase or switch is performed.','',
        '## Handover','',r['messages']['handoff'],'',
        'The packet includes the active section/field script and script version, alongside confirmed answers and the unresolved question. A human can use the same registry shown in the console.','',
        '## Runtime contract','',
        'The registry controls section and field order, questions, clarification, confirmation, aliases, accepted choices, postcode validation and retry limits. The optional model receives the same field specification. Models propose only the requested value; the supervisor validates it and asks for confirmation before saving. Unknown is never converted to no. Multiple volunteered fields are not automatically saved in this prototype.','',
        'Transcript and signal processing remain subject to the consent and escalation policy. A signal can preempt collection at any field. Shared wording for review, refusal, opt-out, clarification and handover also lives in the registry.','',
        'Each session is stamped with the script version. After a registry version change and server restart, an older active demo session must be restarted rather than silently changing its script. This is a demo guard; production should retain immutable historical registries to finish in-flight calls.','',
        '## Replace assumptions with supplied material','',
        '1. Map each official Energy field to a key, type, allowed values and validation contract.',
        '2. Review the supplied recording for pacing, phrasing, objections and section transitions.',
        '3. Revise the registry and have the agent team review the intent of every question.',
        '4. Increment the version, regenerate this book, run tests and replay against the real sandbox.','']
(root/'docs/ENERGY_SCRIPTS.md').write_text('\n'.join(lines))
