import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(process.argv[2]||'static');
const source=fs.readFileSync(path.join(root,'camera.js'),'utf8');
const {Camera}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
globalThis.location={protocol:'http:'};
class WS {
  static OPEN=1;static all=[];
  constructor(url){this.url=url;this.readyState=1;this.sent=[];WS.all.push(this);}
  send(row){this.sent.push(JSON.parse(row));}
  close(){this.closed=true;this.readyState=3;}
}
class Peer {close(){this.closed=true;}}
globalThis.WebSocket=WS;globalThis.RTCPeerConnection=Peer;
const video={srcObject:null}, statuses=[];
const camera=new Camera(video,(...row)=>statuses.push(row),()=>{});
assert.equal(WS.all.length,0,'opening the console must not request camera frames');
camera.connect('duck.local',8443);const ws=camera.ws;
await camera.message({type:'welcome'});assert.deepEqual(ws.sent,[{type:'list'}]);
await camera.message({type:'list',producers:[{id:'camera'}]});
await camera.message({type:'list',producers:[{id:'camera'}]});
assert.deepEqual(ws.sent[1],{type:'startSession',peerId:'camera'});assert.equal(ws.sent.length,2);
await camera.message({type:'sessionStarted',sessionId:'a'});const pc=camera.pc;
camera.disconnect();assert.deepEqual(ws.sent[2],{type:'endSession',sessionId:'a'});
assert.ok(ws.closed&&pc.closed);assert.equal(video.srcObject,null);
assert.match(statuses.at(-1)[1],/最后一个.*休眠/);
camera.disconnect(false);assert.equal(ws.sent.length,3,'pagehide plus unload must be idempotent');
camera.connect('duck.local',8443);assert.notEqual(camera.ws,ws);camera.disconnect(false);
assert.ok(WS.all.flatMap(ws=>ws.sent).every(row=>!('method' in row)),'camera exit must not command robotd');
const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
assert.match(app,/addEventListener\('pagehide',\(\)=>camera\.disconnect\(false\)\)/);
assert.match(app,/采集休眠 · mediad 在线/);
console.log('PASS camera stays disconnected on page open, one video request, session release, idempotent page exit, fresh reconnect and sleep status');
