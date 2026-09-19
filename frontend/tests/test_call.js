import {test} from 'node:test';
import assert from 'node:assert/strict';
import Call from '../src/call.js';

const results=(...parts)=>({resultIndex:0,results:Object.assign(parts.map(([transcript,isFinal,confidence=0.9])=>
  Object.assign([{transcript,confidence}],{isFinal})),{length:parts.length})});
function fixture(options={}) {
  const started=[],captions=[],finals=[],stages=[],errors=[],timers=new Map(); let id=0;
  class Recognition {
    constructor(){this.aborts=0;started.push(this);}
    start(){this.onstart?.();}
    abort(){this.aborts++;}
  }
  const call=new Call({Recognition,onCaption:c=>captions.push(c),onStage:s=>stages.push(s),
    onError:e=>errors.push(e),onFinal:(text,confidence)=>finals.push({text,confidence}),
    schedule:(fn,ms)=>{timers.set(++id,{fn,ms});return id;},unschedule:key=>timers.delete(key),...options});
  const tick=()=>{const [key,timer]=timers.entries().next().value;timers.delete(key);timer.fn();};
  return {call,started,captions,finals,stages,errors,timers,tick};
}

test('the line stays open with interim words captioned live, and sends one turn after a pause',()=>{
  const f=fixture(); f.call.open(); f.call.listen();
  const mic=f.started[0];
  assert.equal(mic.continuous,true); assert.equal(mic.interimResults,true); assert.equal(mic.lang,'en-AU');
  mic.onresult(results(['my postcode is',false]));
  assert.equal(f.captions.at(-1),'my postcode is'); assert.equal(f.finals.length,0);
  mic.onresult(results(['my postcode is 2000',true,0.82]));
  assert.equal([...f.timers.values()][0].ms,1200); // Not sent while the caller may still be speaking.
  f.tick();
  assert.deepEqual(f.finals,[{text:'my postcode is 2000',confidence:0.82}]);
  assert.equal(mic.aborts,1); // One turn at a time: the assistant answers before the mic reopens.
  assert.equal(f.stages.at(-1),'thinking'); assert.equal(f.captions.at(-1),'');
});

test('a sentence continued after a brief pause is sent as one turn, not two',()=>{
  const f=fixture(); f.call.open(); f.call.listen();
  const mic=f.started[0];
  mic.onresult(results(['I rent,',true]));
  assert.equal(f.timers.size,1);
  mic.onresult(results(['and I have solar',false]));
  assert.equal(f.timers.size,0); // The pending send is cancelled while words keep arriving.
  mic.onresult(results(['and I have solar',true]));
  f.tick();
  assert.deepEqual(f.finals,[{text:'I rent, and I have solar',confidence:0.9}]);
});

test('an idle stream closed by the browser reopens instead of ending the call',()=>{
  const f=fixture(); f.call.open(); f.call.listen();
  f.started[0].onend();
  assert.equal(f.started.length,2); assert.equal(f.stages.at(-1),'listening');
});

test('a stream closed mid-turn endpoints the words already heard',()=>{
  const f=fixture(); f.call.open(); f.call.listen();
  const mic=f.started[0]; mic.onresult(results(['gas please',true]));
  mic.onend();
  assert.deepEqual(f.finals,[{text:'gas please',confidence:0.9}]);
  assert.equal(f.started.length,1); // No reopen: the assistant is now replying.
});

test('holding the line drops late results and pending words from the abandoned stream',()=>{
  const f=fixture(); f.call.open(); f.call.listen();
  const mic=f.started[0]; mic.onresult(results(['half a sentence',false]));
  f.call.hold();
  assert.equal(f.captions.at(-1),''); assert.equal(f.timers.size,0); assert.equal(f.stages.at(-1),'holding');
  mic.onresult(results(['late words',true])); mic.onend();
  assert.equal(f.finals.length,0); assert.equal(f.started.length,1);
});

test('reopening after a reply resumes listening, and hanging up does not',()=>{
  const f=fixture(); f.call.open(); f.call.listen(); f.call.hold();
  f.call.listen(); assert.equal(f.started.length,2);
  f.call.close();
  assert.equal(f.started[1].aborts,1); assert.equal(f.stages.at(-1),'');
  f.call.listen(); assert.equal(f.started.length,2);
});

test('a second listen while the microphone is already open does not start a duplicate stream',()=>{
  const f=fixture(); f.call.open(); f.call.listen(); f.call.listen();
  assert.equal(f.started.length,1);
});

test('silence and aborts are pauses in a call, but a denied microphone ends it',()=>{
  const f=fixture(); f.call.open(); f.call.listen();
  const mic=f.started[0];
  mic.onerror({error:'no-speech'}); mic.onerror({error:'aborted'});
  assert.equal(f.errors.length,0); assert.equal(f.call.active,true);
  mic.onerror({error:'not-allowed'});
  assert.match(f.errors.at(-1),/You can still type/);
  assert.equal(f.call.active,false);
});

test('a browser without speech recognition reports it instead of opening a silent call',()=>{
  const f=fixture({Recognition:undefined});
  assert.equal(f.call.open(),false);
  assert.equal(f.call.active,false);
  assert.match(f.errors.at(-1),/continues as text/);
  f.call.listen(); assert.equal(f.started.length,0);
});

test('a flush with nothing heard sends no turn and keeps the caption clear',()=>{
  const f=fixture(); f.call.open(); f.call.listen(); f.call.flush();
  assert.equal(f.finals.length,0); assert.equal(f.captions.at(-1),'');
});
