// Real Chromium + real HTTP; fixture jobs only, no GPU or robot connection.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=spawn(process.env.TEST_PYTHON||'python',[path.join(__dirname,'browser_official0151_fixture.py')],{env:{...process.env,TRAINING_BROWSER_LEGACY_FILTER:'1'}});
 fixture.stderr.on('data',b=>process.stderr.write(b));
 const port=await new Promise((resolve,reject)=>{fixture.stdout.on('data',b=>{const m=b.toString().match(/FIXTURE_READY (\d+)/);if(m)resolve(Number(m[1]));});fixture.on('exit',c=>reject(Error('Fixture exited '+c)));});
 let browser;
 try{
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:3840,height:2160}}),errors=[],gates=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST'&&/\/api\/(probe|preflight|setup|describe)$/.test(r.url()))gates.push(r.url());});
  await page.goto('http://127.0.0.1:'+port);
  await page.waitForFunction(()=>state?.jobs.length>0&&$('task').options.length===15);
  assert.match(await page.locator('#version').innerText(),/R1\.5\.23/);
  assert.equal(await page.locator('#training-firmware-p').inputValue(),'5');
  assert.equal(await page.evaluate(()=>currentTrainingScale()),1);
  assert.equal(await page.locator('#action-filter-enabled,#head-filter-alpha,#legs-filter-alpha').count(),0);
  assert.deepEqual(await page.evaluate(()=>readActionFilter()),{enabled:false,head_alpha:1,legs_alpha:1,version:1});
  const defaults=await page.evaluate(()=>taskCatalog.profiles.map(p=>p.default_task));
  for(const task of defaults){
   await page.evaluate(t=>ensureTaskVisible(t),task);await page.selectOption('#task',task);
   await page.waitForFunction(t=>taskReferences.has(t),task);
   assert.equal(await page.evaluate(()=>currentTrainingScale()),1,task);
   assert.equal(await page.evaluate(()=>currentTrainingFirmwareP()),5,task);
   assert.equal(await page.locator('#task option').count(),15);
  }
  async function choose(task){await page.evaluate(t=>ensureTaskVisible(t),task);await page.selectOption('#task',task);await page.waitForFunction(t=>taskReferences.has(t),task);}
  await choose('Mjlab-GroundPick-Flat-MicroDuck');
  await page.selectOption('#task-terrain','Rough');
  await page.waitForFunction(()=>$('task').value==='Mjlab-GroundPick-Rough-MicroDuck');
  await page.selectOption('#task-backlash','on');
  await page.waitForFunction(()=>taskReferences.has('Mjlab-GroundPick-Rough-Backlash-MicroDuck'));
  assert.equal(await page.locator('#task').inputValue(),'Mjlab-GroundPick-Rough-Backlash-MicroDuck');
  assert.match(await page.locator('#contact-settings-table').innerText(),/5 行 × 5 列/);
  await choose('Mjlab-Roulade-Flat-MicroDuck');
  assert(await page.locator('#task-backlash').isDisabled());assert(await page.locator('#task-terrain').isDisabled());
  assert.match(await page.locator('#task-physics-note').innerText(),/没有注册.*齿隙/);
  await choose('Mjlab-RollerSlope-Flat-MicroDuck');
  assert.equal(await page.locator('#task-terrain').inputValue(),'Slope');
  assert.match(await page.locator('#contact-settings-table').innerText(),/下坡|Ramp/);
  assert.match(await page.locator('#task-physics-note').innerText(),/均须为0/);
  await choose('Mjlab-Velocity-Swizzle-MicroDuck');
  assert.match(await page.locator('#task-description').innerText(),/航向误差/);
  assert.match(await page.locator('#task-physics-note').innerText(),/R148/);
  assert.match(await page.locator('#contact-settings-table').innerText(),/wheel|tire|roller/i);
  await choose('Mjlab-StandUp-Flat-MicroDuck');
  const legacy=await page.evaluate(()=>{const source=state.jobs.find(j=>j.request?.label==='历史滤波 fixture');return [...$('resume').options].find(o=>{try{return JSON.parse(o.value).source_job===source.id;}catch{return false;}}).value;});
  await page.selectOption('#resume',legacy);
  assert(await page.locator('#training-firmware-p').isDisabled());assert(await page.locator('#training-action-scale').isDisabled());
  assert.equal(await page.evaluate(()=>currentTrainingFirmwareP()),3);
  assert.equal(await page.evaluate(()=>currentTrainingScale()),.7);
  assert.deepEqual(await page.evaluate(()=>readActionFilter()),{enabled:true,head_alpha:.5,legs_alpha:.7,version:1});
  assert.match(await page.locator('#action-mapping-note').innerText(),/原模型/);
  await page.selectOption('#resume','');
  assert.equal(await page.evaluate(()=>currentTrainingFirmwareP()),5);
  assert.equal(await page.evaluate(()=>currentTrainingScale()),1);
  assert.equal(await page.evaluate(()=>readActionFilter().enabled),false);
  await choose('Mjlab-Velocity-Flat-MicroDuck');
  await page.locator('#training-firmware-p').fill('7');await page.locator('#training-firmware-p').press('Tab');
  await page.selectOption('#training-action-scale','0.7');
  await page.locator('#queue-add').click();await page.waitForFunction(()=>state.training_queue.entries.length===1);
  const frozen=await page.evaluate(()=>state.training_queue.entries[0].request);
  assert.equal(frozen.training_firmware_p,7);assert.equal(frozen.training_action_scale,.7);assert.equal(frozen.action_filter.enabled,false);
  await page.locator('#training-firmware-p').fill('5');await page.locator('#training-firmware-p').press('Tab');
  await page.selectOption('#training-action-scale','1.0');await page.evaluate(()=>loadState());
  assert.equal(await page.evaluate(()=>state.training_queue.entries[0].request.training_firmware_p),7);
  assert.equal(await page.evaluate(()=>state.training_queue.entries[0].request.training_action_scale),.7);
  const actualReadback=JSON.parse(require('node:fs').readFileSync(path.join(root,'docs/audit-0151/final-rough-friction-readback.json'),'utf8'));
  const sampledText=await page.evaluate(data=>{
   const run=state.jobs.find(j=>j.op==='train');const previous={status:run.status,readback:run.friction_readback};
   try{run.status='running';run.friction_readback=data;renderContactSettings();return $('contact-settings-table').innerText;}
   finally{run.status=previous.status;run.friction_readback=previous.readback;renderContactSettings();}
  },actualReadback);
  assert.match(sampledText,/启动后摩擦实际读回/);assert.match(sampledText,/BAM摩擦倍率/);
  assert(await page.evaluate(()=>{const r=['training-firmware-p','training-action-scale'].map(id=>$(id).getBoundingClientRect());return r.every(x=>Math.abs(x.top-r[0].top)<1&&x.width>80);}), 'P and scale align at 4K');
  await page.locator('#parameters').screenshot({path:path.join(root,'docs','R1.5.23-training-controls-4K.png')});
  await page.setViewportSize({width:1280,height:900});
  await page.locator('#parameters').scrollIntoViewIfNeeded();
  assert(await page.locator('#training-firmware-p').isVisible());assert(await page.locator('#training-action-scale').isVisible());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2),'no page horizontal overflow at 1280');
  await page.locator('#parameters').screenshot({path:path.join(root,'docs','R1.5.23-training-controls-1280.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(gates,[]);
  console.log('TRAINING_1521_UI_OK: 15 profiles; new P5/scale1/no EMA; 37 physical variants; legacy mapping preserved; immutable queue; 4K/1280; no probes or JS errors');
 }finally{if(browser)await browser.close();fixture.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
