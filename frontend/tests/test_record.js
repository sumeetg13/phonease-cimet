import {test} from 'node:test';
import assert from 'node:assert/strict';
import {clock, started, receiptText, filename, NOTE_LABELS} from '../src/record.js';

const summary={session_id:'2f6c9a11b4d3e7f8',lead_id:'synthetic-demo',outcome:'completed',consent:true,
  script_version:'energy-demo-v4',handoff_reason:null,fields:[{key:'postcode',label:'Supply postcode',value:'2000'},{key:'bill_range',label:'Recent bill amount',value:'under 200'}],
  notes:[{at:1000,turn:0,kind:'call',text:'Recovery call opened on a synthetic lead.'},
         {at:1075,turn:4,kind:'concern',text:'Raised hardship, a billing dispute or a vulnerability concern.'}],
  transcript:[{at:1000,turn:0,role:'assistant',text:'May I continue?'},
              {at:1062.5,turn:3,role:'caller',text:'2000'}],
  receipt:{id:'mock-abc123',adapter:'local-mock',payload:{}}};

test('the call clock counts from the first line of the call, not the wall clock',()=>{
  assert.equal(started(summary),1000);
  assert.equal(clock(1000,1000),'00:00');
  assert.equal(clock(1075,1000),'01:15');
  assert.equal(clock(999,1000),'00:00'); // A note written before the first stored line never goes negative.
});

test('the record carries the outcome, the receipt, the details, the notes and the transcript',()=>{
  const text=receiptText(summary);
  assert.match(text,/Outcome: completed/);
  assert.match(text,/Submitted for further processing: receipt mock-abc123 \(local-mock\)/);
  assert.match(text,/- Supply postcode: 2000/);
  assert.match(text,/- Recent bill amount: under 200/);
  assert.match(text,/\[01:15\] Raised: Raised hardship/);
  assert.match(text,/\[00:00\] Assistant: May I continue\?/);
  assert.match(text,/\[01:03\] Caller: 2000/);
  assert.match(text,/audio is not recorded/);
  assert.ok(text.indexOf('CALL NOTES')<text.indexOf('TRANSCRIPT'));
});

test('a call that ended without submitting says so instead of implying a receipt',()=>{
  const text=receiptText({...summary,outcome:'declined',receipt:null,fields:[],notes:[],transcript:[]});
  assert.match(text,/Not submitted: no receipt was issued\./);
  assert.match(text,/DETAILS: none confirmed\./);
  assert.match(text,/CALL NOTES: none\./);
  assert.match(text,/TRANSCRIPT: nothing was stored\./);
  assert.doesNotMatch(text,/mock-abc123/);
});

test('a handover records why the call left the assistant',()=>{
  const text=receiptText({...summary,outcome:'human',handoff_reason:'explicit_human_request',receipt:null});
  assert.match(text,/Outcome: human/);
  assert.match(text,/Handover reason: explicit human request/);
});

test('a call with no consent and a missing record does not throw',()=>{
  assert.equal(receiptText(null),'');
  const text=receiptText({session_id:'x',lead_id:'y',outcome:'declined',consent:false});
  assert.match(text,/Consent: not given/);
  assert.match(text,/TRANSCRIPT: nothing was stored\./);
  assert.equal(filename(null),'phonease-call-session.txt');
  assert.equal(filename(summary),'phonease-call-2f6c9a11b4d3.txt');
});

test('every note kind the agent writes has an operator-facing label',()=>{
  assert.deepEqual(Object.keys(NOTE_LABELS).sort(),
    ['call','concern','consent','detail','escalation','outcome']);
});
