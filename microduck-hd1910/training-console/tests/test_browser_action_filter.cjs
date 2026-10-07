const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=spawn(process.env.TEST_PYTHON||'python',[path.join(__dirname,'browser_official0151_fixture.py')]);
 fixture.stderr.on('data',b=>process.stderr.write(b));
 const port=await new Promise((resolve,reject)=>{fixture.stdout.on('data',b=>{const m=b.toString().match(/FIXTURE_READY (\d+)/);if(m)resolve(Number(m[1]));});fixture.on('exit',c=>reject(Error('Fixture exited '+c)));});
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:3840,height:2160}}),errors=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/\/api\/(probe|preflight|setup)$/.test(r.url()))checks.push(r.url());});
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>state?.jobs.length>0&&$('task').options.length===10);
  assert(await page.locator('#action-filter-enabled').isChecked());
  assert.equal(await page.evaluate(()=>currentTrainingScale()),.9);
  assert.equal(await page.locator('#training-action-scale').inputValue(),'0.9');
  assert(await page.locator('#training-action-scale').isVisible());
  assert(await page.locator('#training-action-scale').isEnabled());
  await page.evaluate(()=>ensureTaskVisible('Mjlab-Velocity-Flat-MicroDuck'));await page.selectOption('#task','Mjlab-Velocity-Flat-MicroDuck');
  for(const scale of ['0.7','1.0','0.9']){
   await page.selectOption('#training-action-scale',scale);
   await page.evaluate(()=>loadState());
   assert.equal(await page.locator('#training-action-scale').inputValue(),scale);
   assert.equal(await page.evaluate(()=>readParameters().training_action_scale),Number(scale));
  }
  await page.selectOption('#training-action-scale','0.7');
  await page.selectOption('#task','Mjlab-SitStand-Flat-MicroDuck');
  assert.equal(await page.locator('#training-action-scale').inputValue(),'1.0');
  assert(await page.locator('#training-action-scale').isDisabled(),'sitstand daemon branch is fixed at 1.0');
  await page.evaluate(()=>ensureTaskVisible('Mjlab-Velocity-Flat-MicroDuck'));await page.selectOption('#task','Mjlab-Velocity-Flat-MicroDuck');
  assert.equal(await page.locator('#training-action-scale').inputValue(),'0.7');
  assert.deepEqual(await page.evaluate(()=>readParameters().action_filter),{enabled:true,head_alpha:.5,legs_alpha:.7,version:1});
  await page.evaluate(()=>ensureTaskVisible('Mjlab-StandUp-Flat-MicroDuck'));await page.selectOption('#task','Mjlab-StandUp-Flat-MicroDuck');await page.evaluate(()=>ensureTaskVisible('Mjlab-Velocity-Flat-MicroDuck'));await page.selectOption('#task','Mjlab-Velocity-Flat-MicroDuck');
  assert(await page.locator('#action-filter-enabled').isChecked());
  const oldValue=await page.evaluate(()=>[...$('resume').options].find(o=>o.value).value);
  await page.selectOption('#resume',oldValue);await page.waitForFunction(()=>$('action-filter-enabled').disabled);
  assert(!(await page.locator('#action-filter-enabled').isChecked()),'legacy resume remains unfiltered');
  assert.match(await page.locator('#runtime-alignment').innerText(),/动作系数 1.*续训沿用原模型/);
  assert.equal(await page.locator('#training-action-scale').inputValue(),'1.0');
  assert(await page.locator('#training-action-scale').isDisabled());
  await page.selectOption('#resume','');assert(await page.locator('#action-filter-enabled').isChecked());
  await page.locator('#head-filter-alpha').fill('0.4');await page.locator('#legs-filter-alpha').fill('0.8');
  assert.deepEqual(await page.evaluate(()=>readParameters().action_filter),{enabled:true,head_alpha:.4,legs_alpha:.8,version:1});
  await page.locator('#action-filter-enabled').uncheck();assert(await page.locator('#head-filter-alpha').isVisible());assert(await page.locator('#head-filter-alpha').isDisabled());
  assert.match(await page.locator('#runtime-alignment').innerText(),/直通 1.0/);
  assert.equal(await page.locator('#training-action-scale').inputValue(),'0.7');
  await page.locator('#action-filter-enabled').check();await page.locator('#head-filter-alpha').fill('0.5');await page.locator('#legs-filter-alpha').fill('0.7');
  await page.locator('#run-label').fill('头腿滤波实验 / Head-leg EMA');
  const response=await page.evaluate(async()=>{
    const parameters=readParameters();const launched=await post('/api/train',parameters);await loadState();
    return state.jobs.find(j=>j.id===launched.job_id).request;
  });
  assert.deepEqual(response.action_filter,{enabled:true,head_alpha:.5,legs_alpha:.7,version:1});
  assert.equal(response.training_action_scale,.7);
  await page.selectOption('#training-action-scale','0.9');
  assert.equal(response.training_adapter_revision,'R1.5.9-current-actions-backlash'); // Queue release leaves physical adapter unchanged.
  assert(await page.evaluate(()=>{const boxes=['training-action-scale','head-filter-alpha','legs-filter-alpha'].map(id=>$(id).getBoundingClientRect());return boxes.every(b=>Math.abs(b.top-boxes[0].top)<1);}),'scale and head/leg fields are aligned in one row');
  await page.locator('#parameters').screenshot({path:path.join(root,'docs','R1.5.11-action-filter-4K.png')});
  assert.equal(checks.length,0,'no environment/preflight gates added');assert.deepEqual(errors,[]);
  console.log('4K SCALE_SELECTOR_OK: .7/.9/1 selectable, polls/task switches preserve selection, request .7 persisted, saved resume mapping retained, no probes/JS errors');
 }finally{await browser.close();fixture.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
