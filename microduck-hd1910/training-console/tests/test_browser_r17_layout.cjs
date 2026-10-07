// Real HTTP/UI fixture, no GPU, WSL, robot or user training processes.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
  const fixture=spawn(process.env.TEST_PYTHON||'python',[path.join(__dirname,'browser_official0151_fixture.py')]);
  fixture.stderr.on('data',b=>process.stderr.write(b));
  const port=await new Promise((resolve,reject)=>{
    fixture.stdout.on('data',b=>{const m=b.toString().match(/FIXTURE_READY (\d+)/);if(m)resolve(Number(m[1]));});
    fixture.on('exit',c=>reject(Error('Fixture exited '+c)));
  });
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox']});
  try{
    const page=await browser.newPage({viewport:{width:3840,height:2160}}),errors=[],checks=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()==='POST'&&/\/api\/(probe|preflight|setup|train|describe)$/.test(r.url()))checks.push(r.url());});
    await page.goto('http://127.0.0.1:'+port);
    await page.waitForFunction(()=>taskReferences.has($('task').value)&&$('reward-fields').children.length>2);
    assert.match(await page.locator('#version').innerText(),/Studio R1\.5\.12/);
    for(const id of ['Mjlab-Velocity-Flat-MicroDuck','Mjlab-StandUp-Flat-MicroDuck','Mjlab-VelStand-Flat-MicroDuck']){
      await page.evaluate(t=>ensureTaskVisible(t),id);await page.selectOption('#task',id);
      await page.waitForFunction(t=>taskReferences.has(t)&&$('reward-fields').children.length>2,id);
      const layout=await page.evaluate(()=>{
        const fields=$('reward-fields'),rect=fields.getBoundingClientRect(),card=$('parameters').getBoundingClientRect();
        return {height:rect.height,gap:card.bottom-rect.bottom,visible:[...fields.children].filter(e=>{
          const r=e.getBoundingClientRect();return r.top>=rect.top&&r.bottom<=rect.bottom;
        }).length,scroll:fields.scrollHeight,cardHeight:card.height,
        courseHeight:document.querySelector('.curriculum-panel').getBoundingClientRect().height,
        overflow:document.documentElement.scrollWidth>innerWidth};
      });
      assert(layout.height>=590,JSON.stringify({id,...layout}));
      assert(layout.visible>=10,JSON.stringify({id,...layout}));
      assert(layout.gap<=24,'reward list fills card, no trailing blank: '+JSON.stringify(layout));
      assert.equal(layout.cardHeight,layout.courseHeight);
      assert.equal(layout.overflow,false);
      await page.evaluate(()=>$('reward-fields').scrollTop=$('reward-fields').scrollHeight);
      assert(await page.evaluate(()=>{
        const box=$('reward-fields').getBoundingClientRect(),last=$('reward-fields').lastElementChild.getBoundingClientRect();
        return last.bottom<=box.bottom+1&&last.top>=box.top;
      }),'the last reward row is accessible at the bottom');
      await page.evaluate(()=>$('reward-fields').scrollTop=0);
      console.log('4K '+id+': '+layout.visible+' complete rewards visible, '+Math.round(layout.height)+'px list, bottom gap '+Math.round(layout.gap)+'px');
    }
    await page.selectOption('#task','Mjlab-Velocity-Flat-MicroDuck');
    await page.waitForFunction(()=>$('task-description').textContent.includes('行走热启动'));
    assert(await page.evaluate(()=>{
      const left=document.querySelector('.parameter-settings').getBoundingClientRect(),right=document.querySelector('.reward-settings').getBoundingClientRect();
      return Math.abs(left.top-right.top)<1&&left.right<=right.left;
    }),'ordinary settings and rewards start at the same height in two columns');
    await page.locator('#parameters').scrollIntoViewIfNeeded();
    const anchored=await page.evaluate(()=>({page:scrollY,left:document.querySelector('.parameter-settings').getBoundingClientRect().top}));
    if(await page.evaluate(()=>$('reward-fields').scrollHeight>$('reward-fields').clientHeight+1)){
    await page.locator('#reward-fields').hover();await page.mouse.wheel(0,350);
    await page.waitForFunction(()=>$('reward-fields').scrollTop>0);
    const afterScroll=await page.evaluate(()=>({page:scrollY,left:document.querySelector('.parameter-settings').getBoundingClientRect().top}));
    assert.deepEqual(afterScroll,anchored,'reward scroll must not move other settings or the page');
    await page.evaluate(()=>$('reward-fields').scrollTop=0);
    }else{console.log('All rewards already fit without scrolling');}
    const palette=await page.evaluate(()=>{
      const style=id=>getComputedStyle($(id));
      return {background:getComputedStyle(document.body).backgroundColor,
        panel:style('parameters').backgroundColor,course:getComputedStyle(document.querySelector('.curriculum-panel')).backgroundColor,
        primary:style('train-start').backgroundColor,input:style('learning-rate').backgroundColor,
        button:style('task-config-refresh').backgroundColor,calibration:style('calibration-zero').backgroundColor};
    });
    assert.equal(palette.background,'rgb(13, 17, 19)');
    assert.equal(palette.panel,'rgb(21, 28, 31)');
    assert.equal(palette.course,palette.panel);
    assert.equal(palette.primary,'rgb(193, 245, 119)');
    assert.equal(palette.input,'rgb(16, 23, 25)');
    assert.equal(palette.button,palette.calibration);
    await page.locator('#parameters').screenshot({path:path.join(root,'docs','R1.5.12-parameters-4K.png')});
    assert(await page.evaluate(()=>CSS.supports('appearance','base-select')),'the deployed Chrome supports the themeable native picker');
    await page.locator('#activation').click();
    await page.waitForFunction(()=>$('activation').matches(':open'));
    await page.locator('#activation option[value="elu"]').hover();
    const picker=await page.evaluate(()=>({
      appearance:getComputedStyle($('activation'),'::picker(select)').appearance,
      background:getComputedStyle($('activation'),'::picker(select)').backgroundColor,
      selected:getComputedStyle($('activation').querySelector('option:checked')).backgroundColor,
      hover:getComputedStyle($('activation').querySelector('option[value="elu"]')).backgroundColor
    }));
    assert.equal(picker.appearance,'base-select');
    assert.equal(picker.background,'rgb(16, 23, 25)');
    assert.equal(picker.selected,'rgb(34, 45, 34)');
    assert.equal(picker.hover,'rgb(37, 51, 45)');
    await page.locator('#parameters').screenshot({path:path.join(root,'docs','R1.5.6-themed-dropdown-4K.png')});
    await page.locator('#activation option[value="relu"]').click();
    assert.equal(await page.locator('#activation').inputValue(),'relu');
    assert.equal(await page.evaluate(()=>readParameters().activation),'relu','theme picker uses the actual training form value');
    await page.locator('#activation').focus();await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
    assert.equal(await page.locator('#activation').inputValue(),'tanh','native keyboard selection remains usable');
    await page.selectOption('#activation','');
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:path.join(root,'docs','R1.5.6-R17-4K.png')});
    for(const width of [1920,1280,1024,390]){
      await page.setViewportSize({width,height:1080});
      await page.locator('#parameters').scrollIntoViewIfNeeded();
      const bounds=await page.evaluate(()=>{
        const card=$('parameters').getBoundingClientRect(),field=$('reward-fields').getBoundingClientRect();
        return {card:card.width,field:field.height,outside:card.right>innerWidth,hidden:getComputedStyle($('reward-fields')).display==='none'};
      });
      assert(!bounds.outside,JSON.stringify({width,...bounds}));
      assert(!bounds.hidden);
      assert(bounds.field>=190,JSON.stringify({width,...bounds}));
      await page.screenshot({path:path.join(root,'docs','R1.5.6-layout-'+width+'.png')});
      console.log(width+'px: reward list '+Math.round(bounds.field)+'px; controls remain visible');
    }
    assert.deepEqual(errors,[]);assert.deepEqual(checks,[]);
    console.log('R17 palette + reward/course scrolling OK; task changes make no preflight or training POSTs.');
  }finally{await browser.close();fixture.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exit(1)});
