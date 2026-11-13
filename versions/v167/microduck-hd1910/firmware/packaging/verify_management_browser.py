"""Exercise actual management fetch/render in Chromium, including an upgrade race.

Run with Playwright installed; pass an alternative console/static directory to
reproduce against a previous release. Only local read-only subprocesses run.
"""
import functools
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'console'))
from service_control import ServiceTransport
from system_log import SystemLog

STATIC = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'console/static'
CATALOG = {'models': [{'slot':'walk','id':'walk-id','name':'fixture Walk','active':True,'available':True,'sha256':'fixture'}],
           'slots':[], 'management_actions':['advanced-parameters'], 'action_scale':.7,
           'default_action_scale':.7, 'servo_parameters':None,
           'default_servo_parameters':{'kp':3,'kd':0,'torque_limit':681}}


with tempfile.TemporaryDirectory() as directory:
    log = SystemLog(directory)
    transport = ServiceTransport('', '/unused', log)
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_GET(self):
            if self.path != '/': return super().do_GET()
            content=(STATIC/'index.html').read_text().replace('<script type="module" src="/app.js"></script>','').encode()
            self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(content)
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length',0)))
            # Production warm relay and streaming JSON parsing; no robot or motors.
            payload=CATALOG if self.path=='/api/service/models' else {'management_revision':'R17','process_matches':True,'actual_port':'/dev/ttyS2','running':True,'pid':123}
            result=transport._manage([sys.executable,'-c',
                "import sys;print('startup diagnostic',file=sys.stderr);print(sys.argv[1])",json.dumps(payload)],privileged=False)
            content=json.dumps(result).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(content)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(STATIC)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1280,'height':1080})
            page.set_default_timeout(4000)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.evaluate('''async()=>{
              const {ServicePanel}=await import('/service.js');
              const panel=new ServicePanel({service_enabled:true,control_token:'fixture',names:[],ids:[]},()=>{});
              window.m=panel.management;window.sent=[];panel.post=async command=>sent.push(command);
              window.s={service_sample_fresh:true,bus:{build:'1fa8438-feetech-ft6-control.18',mode:'motion',action_scale:.7,head_lowpass:.5,legs_lowpass:.7},service_control:{}};
              m.supported=true;m.s=s;m.options={};m.lastIdentity=`${s.bus.build}/motion`;m.connectionAfter=Infinity;
              window.originalFetch=window.fetch;window.newCatalog='''+json.dumps(CATALOG)+''';
              await m.refresh();
            }''')
            assert page.locator('#management-kp').input_value()=='3'
            assert page.locator('#management-kd').input_value()=='0'
            assert page.locator('#management-torque-limit').input_value()=='681'
            assert page.locator('#management-scale-apply').is_enabled()
            print('PASS real browser -> HTTP -> warm relay -> stdout JSON with stderr diagnostics')

            page.evaluate('''async()=>{
              const model={id:'a481d9f211f31d9476ab1a319fe362a2',name:'倒地起身老师 11000 轮',slot:'stand',available:true,active:false};
              window.fetch=(url,options)=>url==='/api/service/models'?Promise.resolve(new Response(JSON.stringify({...newCatalog,models:[...newCatalog.models,model],manual_recovery:{button:'lb',skill:'stand_test',action_scale:1.0,model}}))):originalFetch(url,options);
              await m.refresh(true);m.selectedSlot='stand';m.paint();
            }''')
            assert '11000' in page.locator('#management-recovery').inner_text()
            assert 'a481d9f211f31d9476ab1a319fe362a2' in page.locator('#management-recovery').inner_text()
            assert '基础系数 1.00' in page.locator('#management-recovery').inner_text()
            assert '自动 Stand 未绑定' in page.locator('#management-target').inner_text()
            print('PASS LB teacher and base scale are visible while automatic Stand stays unbound')

            page.evaluate('''async()=>{
              window.fetch=(url,options)=>url==='/api/service/models'?Promise.resolve(new Response(JSON.stringify({...newCatalog,manual_recovery:{button:'lb',skill:'stand_test',action_scale:1.0,model:{id:'a481d9f211f31d9476ab1a319fe362a2',available:false,error:'Expecting value: line 1 column 1 (char 0)'}}}))):originalFetch(url,options);
              await m.refresh(true);
            }''')
            assert '不可用' in page.locator('#management-recovery').inner_text()
            assert 'Expecting value' in page.locator('#management-recovery').inner_text()
            page.evaluate('()=>{window.fetch=originalFetch;m.selectedSlot="walk";m.paint();}')
            print('PASS broken LB contract exposes the configured ID and actual error without claiming it runs')

            page.evaluate('''async()=>{
              m.catalog=null;m.connectionAfter=Infinity;
              window.fetch=(url,options)=>url==='/api/service/models'?new Promise(resolve=>window.deliverOld=()=>resolve(new Response(JSON.stringify({...newCatalog,management_actions:['action-scale'],default_servo_parameters:undefined})))):originalFetch(url,options);
              window.oldRead=m.refresh(true);
              m.render({...s,service_control:{busy:true,job:{at:1,action:'upgrade-service',status:'running'}}},{});
              window.fetch=originalFetch;
              m.render({...s,service_control:{job:{at:1,action:'upgrade-service',status:'completed'}}},{});
            }''')
            page.wait_for_function("m.catalog?.management_actions?.includes('advanced-parameters') && !m.loading")
            page.evaluate('async()=>{deliverOld();await oldRead;}')
            assert page.locator('#management-scale-apply').is_enabled()
            assert page.evaluate("m.catalog.management_actions.includes('advanced-parameters')")
            print('PASS pre-upgrade delayed response cannot overwrite post-upgrade configuration')

            page.evaluate('''async()=>{
              m.invalidate();m.connectionAfter=Infinity;
              window.fetch=(url,options)=>url==='/api/service/models'?Promise.resolve(new Response(JSON.stringify({message:'fixture malformed management output'}))):originalFetch(url,options);
              await m.refresh(true);
            }''')
            assert page.evaluate('m.catalog===null')
            assert '读取失败' in page.locator('#management-kp-saved').inner_text()
            assert 'fixture malformed management output' in page.locator('#management-scale-status').inner_text()
            page.evaluate('()=>{window.fetch=originalFetch;m.retryAfter=0;m.render(s,{});}')
            page.wait_for_function("m.catalog?.management_actions?.includes('advanced-parameters') && !m.loading")
            assert page.locator('#management-scale-apply').is_enabled()
            print('PASS malformed reply displays its cause and subsequent read recovers')

            page.locator('#management-kp').fill('4');page.locator('#management-kd').fill('1')
            page.locator('#management-torque-limit').fill('700')
            page.evaluate("()=>{m.advanced.$('scale').value='.63';m.paint();}")
            assert page.evaluate('sent.length')==0
            page.on('dialog',lambda d:d.accept())
            page.locator('#management-scale-apply').click()
            assert page.evaluate('sent')==[{'action':'set-action-scale','model':'walk-id','scale':.63,'kp':4,'kd':1,'torque_limit':700,'supported':True}]
            print('PASS reading/editing never writes; one Apply submits all four settings')
            page.evaluate("""async()=>{
              const {ControlPanel}=await import('/control.js');
              window.cp=new ControlPanel({service_enabled:true,control_token:'fixture'},document.querySelector('#control-panel'));
              clearInterval(cp.timer);window.padConnects=0;window.socketOpens=0;
              cp.post=async command=>{if(command.action==='connect')padConnects++;return {accepted:true,available:true}};
              cp.socket={open:async()=>socketOpens++,close:()=>{},request:async()=>({accepted:true})};
              window.padSnapshot={...s,control:{connected:false,webpad:{available:false}},service_control:{busy:false,job:{action:'set-action-scale',status:'completed',result:{input:{status:'recovering'}}}}};
              cp.render(padSnapshot,{});cp.tick();await Promise.resolve();
            }""")
            assert page.evaluate('padConnects')==0, 'browser raced backend SSH recovery'
            assert page.evaluate('socketOpens')==0
            page.evaluate("""async()=>{
              padSnapshot={...padSnapshot,control:{connected:true,webpad:{available:true,real_connected:false}},service_control:{job:{action:'set-action-scale',status:'completed',result:{input:{status:'ready'}}}}};
              cp.render(padSnapshot,{});await cp.connect();cp.render(padSnapshot,{});cp.tick();
            }""")
            assert page.evaluate('padConnects')==0, 'backend confirmed transport should be reused'
            assert page.evaluate('socketOpens')==1
            assert page.evaluate('cp.connected')
            print('PASS backend recovery owns SSH; browser opens one socket after ready without a second handshake')

            page.evaluate("""()=>{
              padSnapshot={...padSnapshot,bus:{...padSnapshot.bus,build:'1fa8438-feetech-ft6-control.22',
                phase:'control',homed:true,policy_enabled:false,home_start_guard:{ready:false,reason:'机身倾斜'},
                loaded_models:{stand_test:{sha256:'a481d9f211f31d9476ab1a319fe362a21ef0879d9fa59442a122845af598268c'}}}};
              cp.render(padSnapshot,{});
            }""")
            assert page.locator('[data-button="lb"]').is_enabled()
            assert '无需先回 HOME' in page.locator('[data-button="lb"]').get_attribute('title')
            page.evaluate("""()=>{
              padSnapshot.bus={...padSnapshot.bus,policy_enabled:true,home_recovery:true,
                active_model:padSnapshot.bus.loaded_models.stand_test,scale_use:'stand_test',
                active_action_scale:1.0,active_target_filters:{head_lowpass:1.0,legs_lowpass:1.0}};
              cp.render(padSnapshot,{});
            }""")
            assert '从当前姿态起身' in page.locator('#control-reason').inner_text()
            assert '结束回 HOME' in page.locator('#control-reason').inner_text()
            assert page.locator('#parameter-actual').inner_text()=='1.000'
            assert page.locator('#parameter-head').inner_text()=='1.00'
            assert page.locator('#parameter-legs').inner_text()=='1.00'
            print('PASS fallen HOME allows LB and direct recovery displays actual scale, filters and HOME return')

            assert not errors,errors
            browser.close()
        log.flush();assert 'startup diagnostic' in log.path.read_text()
    finally:
        server.shutdown();server.server_close();transport.channel.close();log.close()
