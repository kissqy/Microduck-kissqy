import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source=await fs.readFile(new URL('../static/ai-panel.js',import.meta.url),'utf8');
const objects=new Map(),revoked=[],players=[];
class Player{
  constructor(url){this.url=url;this.paused=true;this.events={};players.push(this);}
  addEventListener(name,fn){this.events[name]=fn;}
  async play(){this.paused=false;}
  pause(){this.paused=true;}
}
const context={Blob,atob,Audio:Player,URL:{
  createObjectURL(blob){const url='blob:fixture-'+objects.size;objects.set(url,blob);return url;},
  revokeObjectURL(url){revoked.push(url);}
}};
vm.runInNewContext(source.replace('export class AIPanel','class AIPanel')+';globalThis.Cache=ReplyAudioCache;',context);
const cache=new context.Cache(),otherWindow=new context.Cache();
const one='a'.repeat(32),two='b'.repeat(32),pcm=Buffer.from([1,2,3,4,5,6]);
cache.handle({audio_id:one,sequence:0,phase:'chunk',data:pcm.subarray(0,4).toString('base64')});
cache.handle({audio_id:one,sequence:1,phase:'chunk',data:pcm.subarray(4).toString('base64')});
assert.equal(players.length,0,'receiving audio must never auto-play on the console');
assert.equal(cache.entries.get(one).ready,false);
cache.handle({audio_id:one,sequence:2,phase:'end'});
const clip=cache.entries.get(one),wav=Buffer.from(await clip.blob.arrayBuffer());
assert.equal(wav.toString('ascii',0,4),'RIFF');assert.equal(wav.toString('ascii',8,12),'WAVE');
assert.equal(wav.readUInt32LE(24),24000);assert.equal(wav.readUInt16LE(22),1);assert.equal(wav.readUInt16LE(34),16);
assert.equal(wav.readUInt32LE(40),pcm.length);assert.deepEqual(wav.subarray(44),pcm);
assert.equal(clip.chunks.length,0,'after WAV creation release the temporary raw chunks');
assert.equal(otherWindow.entries.size,0,'each page has its own independent memory');
await cache.toggle(one);assert.equal(players.length,1);assert.equal(players[0].paused,false);
await cache.toggle(one);assert.equal(players[0].paused,true);assert.equal(cache.playing,null);
await cache.toggle(one);players.at(-1).events.ended();assert.equal(cache.playing,null);
cache.handle({audio_id:two,sequence:0,phase:'chunk',data:pcm.toString('base64')});
cache.handle({audio_id:two,sequence:2,phase:'end'});assert.equal(cache.entries.has(two),false,'a missing chunk never becomes a playable truncated clip');
cache.handle({audio_id:two,sequence:5,phase:'chunk',data:pcm.toString('base64')});assert.equal(cache.entries.has(two),false,'opening or reconnecting midway cannot reconstruct old audio');
cache.handle({audio_id:two,sequence:0,phase:'chunk',data:'not base64!'});assert.equal(cache.entries.has(two),false);
await cache.toggle(one);cache.clear();
assert.equal(players.at(-1).paused,true);assert.equal(cache.entries.size,0);assert.equal(cache.bytes,0);assert.ok(revoked.includes(clip.url));
const bounded=new context.Cache(()=>{},55);
for(const id of [one,two]){bounded.handle({audio_id:id,sequence:0,phase:'chunk',data:pcm.toString('base64')});bounded.handle({audio_id:id,sequence:1,phase:'end'});}
assert.equal(bounded.entries.has(one),false);assert.equal(bounded.entries.has(two),true);assert.ok(bounded.bytes<=55);
bounded.clear();otherWindow.clear();
for(const storage of ['localStorage','sessionStorage','indexedDB','getUserMedia'])assert.ok(!source.includes(storage),`audio must not use ${storage}`);
assert.ok(source.includes("addEventListener?.('pagehide'"));assert.ok(source.includes('this.replyAudio.clear()'));
console.log(JSON.stringify({passed:true,scope:'exact native PCM WAV, 24k mono16, per-window RAM, no autoplay/persistence, explicit replay/stop/end, sequence gaps, memory eviction, URL revocation and pagehide cleanup'}));
