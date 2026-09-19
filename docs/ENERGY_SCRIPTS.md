# Energy recovery: shared human and AI script book

Generated from `agent-service/phonease/scripts.json`. Edit the registry, then run `./scripts/export_scripts.py`.

**Version:** energy-demo-v2 · **Status:** draft assumptions

Draft Energy scripts based on the brief only. Five demo fields are assumptions, pending the recording and official field list.

The recording, official field list and sandbox schema have not been supplied. These scripts are not represented as derived from that missing material.

## Opening and consent

Hello, I'm the automated Phonease Energy assistant. This is a synthetic demo. With your permission, we will process and save a transcript; audio is not recorded by this prototype. May I continue?

Do not collect journey fields before affirmative consent. Existing confirmed values are retained; only missing fields are asked. A section introduction is read once when entering that section.

## Energy supply

**Section intent:** Establish the supply area and energy types to collect for this demo.

**Section script:** Let's pick up with the energy supply details.

### Supply postcode (`postcode`)

- **Collect:** Identify the supply postcode, not the mailing postcode.
- **Ask:** What is the four digit postcode for the energy supply address?
- **Clarify:** Please say the four postcode digits one at a time. I mean the postcode where the energy will be supplied.
- **Read back:** The supply postcode is {value}. Have I got that right?
- **Validate:** Exactly four digits; syntactic validation only, not a serviceability check.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** two zero zero zero → 2000

### Energy type (`fuel`)

- **Collect:** Collect which energy services the caller wants to compare.
- **Ask:** Are you comparing electricity, gas, or both?
- **Clarify:** Is it electricity only, gas only, or both electricity and gas?
- **Read back:** You want to compare {value}. Is that correct?
- **Validate:** One of electricity, gas or both.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** electricity / electricity only / power / power only → electricity; gas / gas only → gas; both / electricity and gas / gas and electricity → both

## Property details

**Section intent:** Collect occupancy and solar information without giving product advice.

**Section script:** Next, a couple of details about the property.

### Occupancy (`occupancy`)

- **Collect:** Collect whether the caller owns or rents this property.
- **Ask:** Do you own or rent the property?
- **Clarify:** For this property, are you the owner or a tenant?
- **Read back:** You {value} the property. Is that correct?
- **Validate:** One of own or rent; do not infer from an address.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** own / owner / homeowner / i own it / we own it / i own the property → own; rent / renting / tenant / i rent it / we rent it / i rent the property → rent

### Solar panels (`solar`)

- **Collect:** Record whether solar panels are present at the property.
- **Ask:** Does the property have solar panels?
- **Clarify:** Are there solar panels installed at this property? Please say yes or no.
- **Read back:** Solar panels at the property: {value}. Is that correct?
- **Validate:** Explicit true or false; an unknown answer must not become false.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / we do / there are solar panels / we have solar / i have solar → true; no / we don't have solar / there are no solar panels / no solar / no panels → false

## Moving plans

**Section intent:** Identify whether the caller is moving; no dates or commitments are inferred.

**Section script:** Finally, let's check whether this is a move.

### Moving home (`moving`)

- **Collect:** Record whether this journey concerns moving into the property.
- **Ask:** Are you moving into this property?
- **Clarify:** Is this for a home you are moving into, rather than where you already live?
- **Read back:** Moving into the property: {value}. Is that correct?
- **Validate:** Explicit true or false; do not infer a move date.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / i am / we are / i am moving / we are moving → true; no / i am not / we are not / already live here / i already live here / staying here → false

## Final review

Please review: {summary}. May I submit this demo Energy journey? Say yes to submit, or say change followed by the field name.

`{summary}` is generated only from validated, confirmed fields. A final explicit yes permits mock submission. A named correction reopens that field. No plan purchase or switch is performed.

## Handover

I'll ask an Energy specialist to help. I'll pass on the confirmed details and what needs attention so you do not have to start again.

The packet includes the active section/field script and script version, alongside confirmed answers and the unresolved question. A human can use the same registry shown in the console.

## Runtime contract

The registry controls section and field order, questions, clarification, confirmation, aliases, accepted choices, postcode validation and retry limits. The optional model receives the same field specification. Models propose only the requested value; the supervisor validates it and asks for confirmation before saving. Unknown is never converted to no. Multiple volunteered fields are not automatically saved in this prototype.

Transcript and signal processing remain subject to the consent and escalation policy. A signal can preempt collection at any field. Shared wording for review, refusal, opt-out, clarification and handover also lives in the registry.

Each session is stamped with the script version. After a registry version change and server restart, an older active demo session must be restarted rather than silently changing its script. This is a demo guard; production should retain immutable historical registries to finish in-flight calls.

## Replace assumptions with supplied material

1. Map each official Energy field to a key, type, allowed values and validation contract.
2. Review the supplied recording for pacing, phrasing, objections and section transitions.
3. Revise the registry and have the agent team review the intent of every question.
4. Increment the version, regenerate this book, run tests and replay against the real sandbox.
