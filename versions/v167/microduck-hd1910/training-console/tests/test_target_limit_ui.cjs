'use strict';
// R1.5.24: original AB/recorded-start buttons and result view are retired, historical data intact.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'training/static/index.html'),'utf8'),js=fs.readFileSync(path.join(root,'training/static/training.js'),'utf8');
for(const id of ['target-limit-start','target-limit-recorded-start','target-limit-card','target-limit-file','target-limit-note','target-limit-results','target-limit-download']) {assert(!html.includes('id="'+id+'"'));assert(!js.includes("$('"+id+"')"));}
console.log('TARGET_LIMIT_UI_REMOVED: no dangling DOM handlers');
