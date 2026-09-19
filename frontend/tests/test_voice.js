import {test} from 'node:test';
import assert from 'node:assert/strict';
import Voice from '../src/voice.js';
function fixture() {
  const pending = new Map(), spoken = []; let id = 0;
  const synthesis = {cancel(){}, getVoices(){return [{name:'Default',lang:'en-US'}, {name:'Australian English Enhanced',lang:'en-AU'}];}, speak(u){spoken.push(u);}};
  const player = new Voice({synthesis, Utterance:class {constructor(text){this.text=text;}},
    schedule(fn,ms){pending.set(++id,{fn,ms});return id;}, unschedule(key){pending.delete(key);}});
  function tick(){const [key,timer]=pending.entries().next().value;pending.delete(key);timer.fn();}
  return {player,pending,spoken,tick};
}
test('waits before replying, then pauses between sentences with slower modulated delivery',()=>{
  const f=fixture();f.player.speak('Hello. Is that correct?');
  assert.equal(f.spoken.length,0);assert.equal([...f.pending.values()][0].ms,700);
  f.tick();assert.equal(f.spoken[0].rate,.89);assert.equal(f.spoken[0].voice.lang,'en-AU');
  f.spoken[0].onend();assert.equal([...f.pending.values()][0].ms,520);
  f.tick();assert.equal(f.spoken[1].text,'Is that correct?');assert.equal(f.spoken[1].rate,.86);assert.equal(f.spoken[1].pitch,1.04);
});
test('interruption cancels a reply waiting to begin',()=>{
  const f=fixture();f.player.speak('Hello.');f.player.cancel();assert.equal(f.pending.size,0);assert.equal(f.spoken.length,0);
});
test('interruption cancels sentence pause and ignores late completion callbacks',()=>{
  const f=fixture();f.player.speak('One. Two.');f.tick();const first=f.spoken[0];first.onend();f.player.cancel();first.onend();assert.equal(f.pending.size,0);
});
test('a new reply invalidates old speech callbacks',()=>{
  const f=fixture();f.player.speak('Old. Old again.');f.tick();const old=f.spoken[0];f.player.speak('New.');old.onend();assert.equal(f.pending.size,1);f.tick();assert.equal(f.spoken.at(-1).text,'New.');
});
test('reassuring speech is gentle and list items get short pauses',()=>{
  const f=fixture();f.player.speak("I'm sorry. Postcode: 2000; fuel: gas.");f.tick();assert.equal(f.spoken[0].rate,.84);f.spoken[0].onend();f.tick();f.spoken[1].onend();assert.equal([...f.pending.values()][0].ms,300);
});
test('the caller gets the turn back only when a reply finishes, never when it is interrupted',()=>{
  const done=[];const f=fixture();f.player.onDone=()=>done.push('done');
  f.player.speak('One. Two.');f.tick();f.spoken[0].onend();
  assert.deepEqual(done,[]);f.tick();f.spoken[1].onend();
  assert.deepEqual(done,['done']);
  f.player.speak('Interrupted.');f.tick();const live=f.spoken.at(-1);f.player.cancel();live.onend();
  assert.deepEqual(done,['done']);
});
