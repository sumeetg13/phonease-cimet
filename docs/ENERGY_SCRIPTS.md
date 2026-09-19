# Energy recovery: shared human and AI script book

Generated from `agent-service/phonease/scripts.json`. Edit the registry, then run `./scripts/export_scripts.py`.

**Version:** energy-demo-v4 · **Status:** draft assumptions

Draft Energy comparison scripts based on docs/energy-plan-comparison-data-flow.md. Fields cover the caller's name, supply location, current provider, usage profile and infrastructure add-ons. NMI lookup, CDR smart-meter data sharing, exact bill/feed-in-tariff figures and contact email/phone capture are out of scope for a voice-only demo and are approximated with bucketed ranges or omitted; the official field list and sandbox schema have not been supplied.

The recording, official field list and sandbox schema have not been supplied. These scripts are not represented as derived from that missing material.

## Opening and consent

One variant is chosen at random per call; all convey the same disclosure and consent request.

- Hello, I'm the automated AI Phonease Energy assistant. This is a synthetic demo. With your permission, we will process and save a transcript; May I continue?
- Hi there, I'm an AI agent from Phonease, here to help with your energy journey. This is a synthetic demo — with your permission I'll process and save a transcript. Is that okay to continue?
- Hey, I'm Phonease's automated energy assistant, an AI agent here to assist with your energy journey. This is a synthetic demo; with your permission we'll process and save a transcript. May I go ahead?
- Good day, this is the Phonease AI energy assistant calling. It's a synthetic demo, so with your consent we'll process and save a transcript. Are you happy for me to continue?

Do not collect journey fields before affirmative consent. Existing confirmed values are retained; only missing fields are asked. A section introduction is read once when entering that section.

## Introduction

**Section intent:** Personalize the call with the caller's name before the journey begins.

**Section script variants:**

- Let's start with a quick introduction.
- First, a quick introduction.
- To start, let's get acquainted.

### Caller name (`name`)

- **Collect:** Personalize the rest of the call. No identity verification is performed against this name.
- **Ask:** May I get your full name, please?
- **Clarify:** Sorry, I didn't catch a name there — could you say your full name for me?
- **Read back:** I have your name as {value}. Is that correct?
- **Validate:** A spoken name; letters, spaces, hyphens and apostrophes only, not verified against any record.
- **Failure limit:** 2 failed attempts, then human handover.

## Energy supply

**Section intent:** Establish the supply area and energy types to collect for this demo.

**Section script variants:**

- Let's pick up with the energy supply details.
- First, let's sort out your energy supply details.
- To start, I just need a couple of details about your energy supply.

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

**Section intent:** Collect occupancy information without giving product advice.

**Section script variants:**

- Next, a couple of details about the property.
- Now let's cover a couple of things about the property.
- Moving on, I have a couple of quick property questions.

### Occupancy (`occupancy`)

- **Collect:** Collect whether the caller owns or rents this property.
- **Ask:** Do you own or rent the property?
- **Clarify:** For this property, are you the owner or a tenant?
- **Read back:** You {value} the property. Is that correct?
- **Validate:** One of own or rent; do not infer from an address.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** own / owner / homeowner / i own it / we own it / i own the property → own; rent / renting / tenant / i rent it / we rent it / i rent the property → rent

## Moving plans

**Section intent:** Identify whether the caller is moving; no dates or commitments are inferred.

**Section script variants:**

- Next, let's check whether this is a move.
- Let's confirm whether this is for a move.
- One quick check: is this journey related to a move?

### Moving home (`moving`)

- **Collect:** Record whether this journey concerns moving into the property.
- **Ask:** Are you moving into this property?
- **Clarify:** Is this for a home you are moving into, rather than where you already live?
- **Read back:** Moving into the property: {value}. Is that correct?
- **Validate:** Explicit true or false; do not infer a move date.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / i am / we are / i am moving / we are moving → true; no / i am not / we are not / already live here / i already live here / staying here → false

## Current provider

**Section intent:** Identify the current retailer so any comparison is measured against the right baseline.

**Section script variants:**

- Now, a quick question about your current energy provider.
- Next, let's confirm who currently supplies your energy.
- Let's cover your current energy provider.

### Current provider (`current_provider`)

- **Collect:** Identify the current retailer so any comparison is measured against the right baseline.
- **Ask:** Who is your current energy retailer — for example AGL, Origin, EnergyAustralia, Alinta Energy, or Red Energy?
- **Clarify:** Which company currently supplies your energy? Say the name, or say other if it's not AGL, Origin, EnergyAustralia, Alinta Energy or Red Energy.
- **Read back:** Your current provider is {value}. Is that correct?
- **Validate:** One of the listed retailers, or other.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** agl → agl; origin / origin energy → origin; energyaustralia / energy australia → energyaustralia; alinta / alinta energy → alinta energy; red energy / red → red energy; other / someone else / a different provider / not sure / i'm not sure / i don't know / do not know → other

## Usage profile

**Section intent:** Estimate usage from a recent bill where available, or a household profile otherwise.

**Section script variants:**

- Now let's get a sense of your energy usage.
- Next, a couple of questions about how much energy you use.
- Let's talk about your typical energy usage.

### Recent bill available (`has_bill`)

- **Collect:** Route to the most accurate usage source available: a recent bill, or a household estimate.
- **Ask:** Do you have a recent energy bill handy?
- **Clarify:** Do you have a recent bill in front of you right now? Please say yes or no.
- **Read back:** Recent bill available: {value}. Is that correct?
- **Validate:** Explicit true or false.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / i have one / i have a bill / i've got one → true; no / i don't have one / i don't have a bill / not with me → false

### Recent bill amount (`bill_range`)

- **Collect:** Approximate spend as a proxy for usage when a caller has a bill on hand.
- **Ask:** Roughly, was your last bill under 200 dollars, 200 to 400, 400 to 600, or over 600 dollars?
- **Clarify:** Was it under 200 dollars, 200 to 400, 400 to 600, or over 600 dollars?
- **Read back:** Your last bill was roughly {value} dollars. Is that correct?
- **Validate:** One of the four listed ranges.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** under 200 / less than 200 / under two hundred → under 200; 200 to 400 / two hundred to four hundred / between 200 and 400 → 200 to 400; 400 to 600 / four hundred to six hundred / between 400 and 600 → 400 to 600; over 600 / more than 600 / over six hundred → over 600
- **Asked only if:** `has_bill` is true

### Household size (`household_size`)

- **Collect:** Estimate usage from household size when no bill is available.
- **Ask:** No problem — roughly how many people live in the home: one to two, three to four, or five or more?
- **Clarify:** Roughly how many people live in the home — one to two, three to four, or five or more?
- **Read back:** About {value} people live in the home. Is that correct?
- **Validate:** One of the three listed household sizes.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** one to two / one or two / just me / just us two / one / two → one to two; three to four / three or four / three / four → three to four; five or more / five / six / a big family → five or more
- **Asked only if:** `has_bill` is false

### Swimming pool (`has_pool`)

- **Collect:** Pool pumps are a major, steady load; flags likely higher usage.
- **Ask:** Do you have a swimming pool at the property?
- **Clarify:** Is there a swimming pool at the property? Please say yes or no.
- **Read back:** Swimming pool at the property: {value}. Is that correct?
- **Validate:** Explicit true or false.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / we have a pool / there's a pool → true; no / no pool / we don't have a pool → false
- **Asked only if:** `has_bill` is false

### Ducted air conditioning (`has_ducted_ac`)

- **Collect:** Ducted air conditioning is a major seasonal load; flags likely higher usage.
- **Ask:** Do you have ducted air conditioning?
- **Clarify:** Is there ducted air conditioning installed? Please say yes or no.
- **Read back:** Ducted air conditioning: {value}. Is that correct?
- **Validate:** Explicit true or false.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / we have ducted / we have ducted air conditioning → true; no / no ducted air conditioning / we don't have ducted → false
- **Asked only if:** `has_bill` is false

### Electric vehicle (`has_ev`)

- **Collect:** Home EV charging is a major load; flags likely higher usage.
- **Ask:** Do you have an electric vehicle you charge at home?
- **Clarify:** Do you charge an electric vehicle at home? Please say yes or no.
- **Read back:** Electric vehicle charged at home: {value}. Is that correct?
- **Validate:** Explicit true or false.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / we have an ev / we charge an electric car → true; no / no electric vehicle / we don't have an ev → false
- **Asked only if:** `has_bill` is false

## Solar

**Section intent:** Record solar presence and approximate system size.

**Section script variants:**

- Now, let's cover solar.
- A quick question about solar panels.
- Let's check on solar at the property.

### Solar panels (`solar`)

- **Collect:** Record whether solar panels are present at the property.
- **Ask:** Does the property have solar panels?
- **Clarify:** Are there solar panels installed at this property? Please say yes or no.
- **Read back:** Solar panels at the property: {value}. Is that correct?
- **Validate:** Explicit true or false; an unknown answer must not become false.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / we do / there are solar panels / we have solar / i have solar → true; no / we don't have solar / there are no solar panels / no solar / no panels → false

### Solar system size (`solar_size`)

- **Collect:** Approximate solar export capacity to help scope feed-in-tariff sensitive plans.
- **Ask:** Roughly what size is the solar system — under 5 kilowatts, 5 to 10 kilowatts, or over 10 kilowatts?
- **Clarify:** Is the solar system under 5 kilowatts, 5 to 10 kilowatts, or over 10 kilowatts?
- **Read back:** The solar system is roughly {value}. Is that correct?
- **Validate:** One of the three listed size ranges.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** under 5 / under 5kw / small / less than 5 kilowatts → under 5kw; 5 to 10 / 5 to 10kw / medium / five to ten kilowatts → 5 to 10kw; over 10 / over 10kw / large / more than 10 kilowatts → over 10kw
- **Asked only if:** `solar` is true

## Concession eligibility

**Section intent:** Identify concession card eligibility for potential rebates.

**Section script variants:**

- Last, a question about concession eligibility.
- One final question about concession cards.
- Almost done — just a concession card question.

### Concession card (`concession_card`)

- **Collect:** Identify concession card eligibility for potential state government rebates.
- **Ask:** Do you hold a Pensioner Concession Card or a Health Care Card?
- **Clarify:** Do you hold a Pensioner Concession Card or a Health Care Card? Please say yes or no.
- **Read back:** Concession card holder: {value}. Is that correct?
- **Validate:** Explicit true or false.
- **Failure limit:** 2 failed attempts, then human handover.
- **Examples of accepted phrasing:** yes / i have one / i hold a concession card / i have a health care card → true; no / i don't have one / no concession card → false

## Final review

Please review: {summary}. Should we submit these details for further processing? Say yes to submit, or say change followed by the field name.

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
