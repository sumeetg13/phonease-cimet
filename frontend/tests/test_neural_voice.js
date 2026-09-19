import {test} from 'node:test';
import assert from 'node:assert/strict';
import NeuralVoice from '../src/neural-voice.js';

const session={id:'synthetic-session',revision:2,state:'collecting',message:'Not sent by browser'};
const response=()=>({ok:true,headers:new Headers({'Content-Type':'audio/mpeg'}),blob:async()=>new Blob(['ID3-audio'])});
function fixture(fetcher=async()=>response()) {
  const requests=[],status=[],revoked=[],timers=new Map(); let id=0;
  const audio={src:'',plays:0,pauses:0,currentTime:0,
    play(){this.plays++;return Promise.resolve();},pause(){this.pauses++;},
    removeAttribute(){this.src='';},load(){}};
  const player=new NeuralVoice({audio,getToken:()=> 'operator-token',onStatus:s=>status.push(s),
    fetcher:(url,options)=>{requests.push({url,...options});return fetcher(url,options);},
    urls:{createObjectURL:()=> 'blob:test',revokeObjectURL:url=>revoked.push(url)},
    schedule:(fn)=>{timers.set(++id,fn);return id;},unschedule:key=>timers.delete(key)});
  return {player,audio,requests,status,revoked,timers};
}
test('neural speech sends session identity, never text or OpenAI credentials',async()=>{
  const f=fixture(); await f.player.speak(session);
  assert.deepEqual(JSON.parse(f.requests[0].body),{session_id:session.id,revision:2});
  assert.equal(f.requests[0].headers.Authorization,'Bearer operator-token');
  assert.equal(f.audio.src,'blob:test'); assert.equal(f.audio.plays,1);
  assert.equal(f.timers.size,0); assert.equal(f.status.at(-1),'Playing OpenAI neural voice');
});
test('cancel pauses audio, clears source, releases blob and ignores late callbacks',async()=>{
  const f=fixture(); await f.player.speak(session); const ended=f.audio.onended;
  f.player.cancel(); ended(); assert.equal(f.audio.src,''); assert.deepEqual(f.revoked,['blob:test']);
  assert.equal(f.status.at(-1),'');
});
test('late synthesis cannot play after interruption even if transport ignores abort',async()=>{
  let resolve; const f=fixture(()=>new Promise(r=>resolve=r));
  const pending=f.player.speak(session); f.player.cancel(); resolve(response()); await pending;
  assert.equal(f.requests[0].signal.aborted,true); assert.equal(f.audio.plays,0); assert.equal(f.timers.size,0);
});
test('late blob cannot play after interruption',async()=>{
  let resolve; const f=fixture(async()=>({...response(),blob:()=>new Promise(r=>resolve=r)}));
  const pending=f.player.speak(session); await Promise.resolve(); f.player.cancel();
  resolve(new Blob(['old'])); await pending; assert.equal(f.audio.plays,0);
});
test('autoplay block is visible and replay reuses audio without another paid request',async()=>{
  const f=fixture(); f.audio.play=()=>Promise.reject(Object.assign(new Error(),{name:'NotAllowedError'}));
  await f.player.speak(session); assert.match(f.status.at(-1),/Press Replay/);
  f.audio.play=()=>Promise.resolve(); await f.player.replay(session);
  assert.equal(f.requests.length,1); assert.equal(f.status.at(-1),'Playing OpenAI neural voice');
});
test('provider failure stays visible instead of silently using device speech',async()=>{
  const f=fixture(async()=>({ok:false})); await f.player.speak(session);
  assert.match(f.status.at(-1),/Neural speech unavailable/); assert.equal(f.audio.plays,0); assert.equal(f.timers.size,0);
});
test('a new reply invalidates the old request',async()=>{
  let resolve; const f=fixture(()=>f.requests.length===1?new Promise(r=>resolve=r):Promise.resolve(response()));
  const old=f.player.speak(session); await f.player.speak({...session,revision:3}); resolve(response()); await old;
  assert.equal(f.audio.plays,1); assert.equal(f.player.key,`${session.id}:3`);
});
test('timeout aborts a stuck request and clears state',async()=>{
  const f=fixture((_,options)=>new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('aborted')))));
  const pending=f.player.speak(session); [...f.timers.values()][0](); await pending;
  assert.equal(f.requests[0].signal.aborted,true); assert.match(f.status.at(-1),/unavailable/); assert.equal(f.timers.size,0);
});
test('accepted human session never generates or replays AI speech',async()=>{
  const f=fixture(); await f.player.speak({...session,state:'human'}); await f.player.replay({...session,state:'human'});
  assert.equal(f.requests.length,0); assert.equal(f.audio.plays,0);
});
test('repeated replay clicks while synthesis is pending do not duplicate paid requests',async()=>{
  let resolve; const f=fixture(()=>new Promise(r=>resolve=r));
  const pending=f.player.speak(session); await f.player.replay(session); await f.player.replay(session);
  assert.equal(f.requests.length,1); resolve(response()); await pending;
});
test('default browser functions are not invoked with the player as their receiver',async()=>{
  const original={fetch:globalThis.fetch,setTimeout:globalThis.setTimeout,clearTimeout:globalThis.clearTimeout};
  const f=fixture();
  try {
    globalThis.fetch=function(){assert.equal(this,undefined);return Promise.resolve(response());};
    globalThis.setTimeout=function(){assert.equal(this,undefined);return 1;};
    globalThis.clearTimeout=function(){assert.equal(this,undefined);};
    const player=new NeuralVoice({audio:f.audio,getToken:()=> 'test',urls:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}}});
    await player.speak(session); assert.equal(f.audio.plays,1); player.cancel();
  } finally {Object.assign(globalThis,original);}
});
test('the caller gets the turn back when playback ends, fails or is blocked, but not on interruption',async()=>{
  const done=[];const f=fixture();f.player.onDone=()=>done.push('done');
  await f.player.speak(session);f.audio.onended();
  assert.deepEqual(done,['done']);
  f.audio.onerror();assert.deepEqual(done,['done','done']);
  const blocked=fixture();blocked.player.onDone=()=>done.push('blocked');
  blocked.audio.play=()=>Promise.reject(Object.assign(new Error('gesture'),{name:'NotAllowedError'}));
  await blocked.player.speak(session);
  assert.equal(done.at(-1),'blocked');
  const failed=fixture(async()=>{throw new Error('provider down');});
  failed.player.onDone=()=>done.push('failed');
  await failed.player.speak(session);
  assert.equal(done.at(-1),'failed');
  const interrupted=fixture();interrupted.player.onDone=()=>done.push('interrupted');
  await interrupted.player.speak(session);const ended=interrupted.audio.onended;
  interrupted.player.cancel();ended?.();
  assert.notEqual(done.at(-1),'interrupted');
});
