'use strict';
// R1.5.24: former manual recovery-check GUI was retired; task and PPO recovery remain.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'training/static/index.html'),'utf8'),js=fs.readFileSync(path.join(root,'training/static/training.js'),'utf8');
for(const name of ['recovery-eval-start','recovery-eval-note']) {assert(!html.includes('id="'+name+'"'));assert(!js.includes("$('"+name+"')"));}
for(const name of ['preview-start','play-start','export-model'])assert(html.includes('id="'+name+'"'));
console.log('RECOVERY_CHECK_UI_REMOVED: ordinary policy evaluation remains');
