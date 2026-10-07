// Real HTTP + desktop scheduler, no GPU; explicit fixture completion events.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
 const fixture=spawn(process.env.TEST_PYTHON||'python',[path.join(__dirname,'browser_queue_fixture.py')]);
 fixture.stderr.on('data',b=>process.stderr.write(b));
 const port=await new Promise((resolve,reject)=>{fixture.stdout.on('data',b=>{const m=b.toString().match(/FIXTURE_READY (\d+)/);if(m)resolve(Number(m[1]));});fixture.on('exit',c=>reject(Error('fixture exit '+c)));});
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({viewport:{width:3840,height:2160}}),errors=[],posts=[];
  let page=await context.newPage();
  const observe=p=>{p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});};observe(page);
  await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>!!studioData&&!!state?.training_queue&&!!token);
  assert(await page.locator('#train-start').isDisabled());
  assert.equal(await page.locator('#queue-start,#queue-pause,.command-bar').count(),0);
  assert.equal(await page.locator('#training-queue #selected-action').count(),1);
  assert.equal(await page.locator('#parameters #contact-settings').count(),1);
  async function add(task,label){
   await page.evaluate(t=>ensureTaskVisible(t),task);await page.selectOption('#task',task);
   await page.fill('#run-label',label);await page.fill('#iterations','2000');
   await page.locator('#queue-add').click();await page.waitForFunction(name=>state.training_queue.entries.some(e=>e.request.label===name),label);
  }
  await add('Mjlab-Velocity-Rough-Backlash-MicroDuck','夜间行走老师');
  await add('Mjlab-StandUp-Rough-Backlash-MicroDuck','夜间起身老师');
  await page.evaluate(()=>ensureTaskVisible('Mjlab-VelStand-Rough-Backlash-MicroDuck'));await page.selectOption('#task','Mjlab-VelStand-Rough-Backlash-MicroDuck');
  for(const role of ['walk','stand']){
   const future=await page.locator('#'+role+'-teacher option').evaluateAll(o=>o.find(x=>x.text.startsWith('队列老师')).value);
   await page.selectOption('#'+role+'-teacher',future);
  }
  await page.fill('#run-label','夜间联合训练');await page.fill('#iterations','2000');await page.locator('#queue-add').click();
  await page.waitForFunction(()=>state.training_queue.entries.length===3);
  assert.equal(await page.locator('.queue-row').count(),3);
  assert.match(await page.locator('#queue-list').innerText(),/动作 0.9.*滤波 0.5\/0.7/);
  // Page edits must not mutate the snapshots waiting in the queue.
  await page.fill('#num-envs','2048');await page.selectOption('#training-action-scale','0.7');
  assert(await page.evaluate(()=>state.training_queue.entries.every(e=>e.request.num_envs===4096&&e.request.training_action_scale===.9)));
  await page.locator('#training-queue').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(root,'docs','R1.5.12-queue-4K.png'),fullPage:false});
  const ids=await page.evaluate(()=>state.training_queue.entries.map(e=>e.id));
  // A dependent joint task cannot move ahead of its queued teachers.
  await page.locator(`[data-entry="${ids[2]}"][data-queue-direction="-1"]`).click();
  await page.waitForFunction(()=>$('toast').textContent.includes('老师后面'));
  await page.locator('#train-start').click();await page.waitForFunction(()=>state.training_queue.entries[0].job_id);
  const first=await page.evaluate(()=>state.training_queue.entries[0].job_id);
  assert(await page.locator('#train-start').isDisabled());
  assert.match(await page.locator('#selected-action').innerText(),/当前训练.*夜间行走老师/);
  assert.match(await page.locator('#training-summary').innerText(),/4,096 环境/);
  const finish=async(id,status='completed')=>{
   const r=await context.request.post('http://127.0.0.1:'+port+'/fixture/finish',{headers:{'X-Training-Token':'queue-test-token'},data:{job_id:id,status}});assert(r.ok());
  };
  // The scheduler continues without any browser page open.
  await page.close();await finish(first);
  await new Promise(resolve=>setTimeout(resolve,1200));
  page=await context.newPage();observe(page);await page.goto('http://127.0.0.1:'+port);
  await page.waitForFunction(()=>state?.training_queue?.entries[1].job_id);
  const second=await page.evaluate(()=>state.training_queue.entries[1].job_id);
  assert.equal(await page.evaluate(()=>state.training_queue.entries[0].status),'completed');
  assert.equal(await page.evaluate(()=>state.jobs.filter(j=>j.op==='train').length),2);
  await finish(second);await page.waitForFunction(()=>state.training_queue.entries[1].status==='completed');
  await page.waitForFunction(()=>state.training_queue.entries[2].job_id);
  const third=await page.evaluate(()=>state.training_queue.entries[2].job_id);
  const joint=await page.evaluate(id=>state.jobs.find(j=>j.id===id),third);
  assert.equal(joint.request.joint.walk.checkpoint,'/fixture/'+first+'/model_1999.pt');
  assert.equal(joint.request.joint.stand.checkpoint,'/fixture/'+second+'/model_1999.pt');
  assert.equal(joint.request.training_action_scale,.9);
  await finish(third,'failed');await page.waitForFunction(()=>state.training_queue.entries[2].status==='failed'&&!state.training_queue.enabled);
  assert.match(await page.locator('#queue-message').innerText(),/暂停/);
  await page.locator(`[data-entry="${ids[2]}"][data-queue-action="retry"]`).click();
  await page.waitForFunction(()=>state.training_queue.entries[2].status==='waiting');
  await page.locator('#train-start').click();await page.waitForFunction(old=>state.training_queue.entries[2].job_id&&state.training_queue.entries[2].job_id!==old,third);
  const retried=await page.evaluate(()=>state.training_queue.entries[2].job_id);
  await finish(retried);await page.waitForFunction(()=>state.training_queue.entries.every(e=>e.status==='completed')&&!state.training_queue.enabled);
  await page.locator('#queue-clear').click();await page.waitForFunction(()=>state.training_queue.entries.length===0);
  assert(await page.locator('#train-start').isDisabled(),'one task must be added before start');
  await page.evaluate(t=>ensureTaskVisible(t),'Mjlab-Velocity-Rough-Backlash-MicroDuck');await page.selectOption('#task','Mjlab-Velocity-Rough-Backlash-MicroDuck');
  await page.waitForFunction(()=>document.querySelector('[data-contact-edit*="foot_friction"]'));
  assert.match(await page.locator('#contact-settings-table').innerText(),/0.7,1.3/);
  assert.match(await page.locator('#contact-settings-table').innerText(),/Contact capacity.*nconmax/);
  await page.locator('[data-contact-edit*="foot_friction"][data-contact-edit*="ranges"]').click();
  await page.locator('[data-contact-input]').fill('[0.8,1.2]');await page.locator('[data-contact-input]').press('Tab');
  await page.waitForFunction(()=>studioDraft.task_overrides[$('task').value]?.some(p=>p.path.includes('foot_friction')&&p.value[0]===.8)&&!studioDirty);
  await add('Mjlab-Velocity-Rough-Backlash-MicroDuck','单项停止测试');
  assert(await page.evaluate(()=>!('recipe' in state.training_queue.entries[0])),'queue API does not leak full recipes');
  await page.locator('#train-start').click();await page.waitForFunction(()=>state.training_queue.entries[0].job_id);
  const single=await page.evaluate(()=>state.training_queue.entries[0].job_id);
  assert(await page.evaluate(()=>state.jobs.find(j=>j.op==='train'&&j.id===state.training_queue.entries[0].job_id).request.studio_recipe.task_overrides['Mjlab-Velocity-Rough-Backlash-MicroDuck'].some(p=>p.path.includes('foot_friction')&&p.value[0]===.8)));
  await add('Mjlab-Velocity-Rough-Backlash-MicroDuck','停止后保留下一项');
  await page.locator('#train-stop').click();
  await page.waitForFunction(()=>!state.training_queue.enabled&&state.jobs.find(j=>j.id===state.training_queue.entries[0].job_id).status==='stopping');
  await finish(single,'stopped');await page.waitForFunction(()=>state.training_queue.entries[0].status==='stopped');
  assert.equal(await page.evaluate(()=>state.training_queue.entries[1].status),'waiting');
  assert.equal(await page.evaluate(()=>state.training_queue.entries[1].job_id),undefined);
  await page.locator('#train-start').click();await page.waitForFunction(()=>state.training_queue.entries[1].job_id);
  const next=await page.evaluate(()=>state.training_queue.entries[1].job_id);
  await finish(next);await page.waitForFunction(()=>!state.training_queue.enabled&&state.training_queue.entries[1].status==='completed');
  for(const width of [1920,1280,1024,390]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.equal(posts.filter(p=>/\/api\/(setup|preflight|probe|describe)$/.test(p)).length,0);
  assert.equal(posts.filter(p=>/\/api\/train$/.test(p)).length,0,'all training starts through the queue');
  assert.deepEqual(errors,[]);
  console.log('PASS queue: mandatory single-task queue, contact edits in snapshots, actual header, future teachers/latest PT, sequential dispatch without page, unified stop/retained next task, failure/retry, 4K/mobile; no probes/direct starts.');
 }finally{await browser.close();fixture.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
