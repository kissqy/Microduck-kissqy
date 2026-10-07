"""Rebuild reference-only facts from downloaded official HTML, never a training preset.

Usage: python tools/build_servo_reference.py /path/to/robotis-xl330-current.html
Requires beautifulsoup4 + lxml only for this maintenance command.
"""
import hashlib
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'data/servo_references.json'
data = json.loads(PATH.read_text())
html = Path(sys.argv[1]).read_bytes()
soup = BeautifulSoup(html, 'lxml')
data.update(schema='microduck-servo-reference/v2', reviewed_on='2026-10-03',
            manufacturer_source='https://docs.robotis.com/docs/dxl/model_reference/x_series/xl_series/xl330-m288/',
            manufacturer_html_sha256=hashlib.sha256(html).hexdigest())

def fields(rows):
    return {k:dict(title=zh,english=en,unit=unit,explanation=meaning) for k,zh,en,unit,meaning in rows}

data['actuator_fields'] = fields([
 ('target_names_expr','驱动关节选择','Actuated joint selection','名称/正则','决定哪些关节由BAM驱动；14个策略关节不含鸭嘴。'),
 ('transmission_type','传动对象','Transmission type','类型','joint表示关节驱动，不是IMU或相机site。'),
 ('armature','配置层转子惯量','Config armature','kg·m²','当前BAM用辨识文件的armature；此处null不是零惯量。'),
 ('frictionloss','配置层干摩擦','Config friction loss','N·m','BAM每个物理步写入动态摩擦，此处不是最终摩擦值。'),
 ('viscous_damping','配置层黏性阻尼','Config viscous damping','N·m·s/rad','BAM每步写入friction_viscous；此处null不等于无阻尼。'),
 ('delay_min_lag','最小指令延迟','Minimum command lag','物理步','乘物理步长换成时间；当前3×5ms=15ms。'),
 ('delay_max_lag','最大指令延迟','Maximum command lag','物理步','当前6×5ms=30ms，不是6个20ms策略周期。'),
 ('delay_hold_prob','保留延迟的概率','Delay hold probability','0～1','延迟更新时继续使用上一延迟的概率。'),
 ('delay_update_period','延迟更新周期','Delay update period','物理步','0表示每个物理步均可更新延迟。'),
 ('delay_per_env_phase','独立延迟相位','Independent delay phase','开关','使各并行环境错开延迟更新。'),
 ('motor_name','内置电机名称','Bundled motor name','名称','官方通过xl330选BAM资产；飞特通过自定义JSON选择。'),
 ('model','内置模型系列','Bundled model family','名称','使用内置资产时选择m6；JSON路径模式在文件内定义系列。'),
 ('json_path','自定义辨识文件','Custom identification JSON','路径','飞特实际加载hd1910_m6.json或本次覆盖文件。'),
 ('vin','固定仿真电压','Fixed simulation voltage','V','vin_range存在时优先使用范围；null沿用BAM电机类默认值。'),
 ('kp_fw','模型固件P值','Firmware proportional gain','raw','两种舵机的增益换算不同；200和5不能直接按40倍比较力度。'),
 ('vin_range','仿真供电范围','Supply voltage range','V','每个环境启动时抽样，描述训练电气模型，不是厂家允许电压。'),
 ('vin_drop_gain_range','负载压降系数','Load voltage drop gain','V/(N·m)','压降=系数×各驱动关节上一物理步的绝对电机扭矩之和。'),
 ('vin_min','仿真压降下限','Voltage sag floor','V','负载压降后电压不会低于该值；真实掉压若更低，仿真不会覆盖。'),
 ('stiff_frictionloss','强化静摩擦约束','Stiff friction constraint','开关','使用较硬的MuJoCo摩擦约束减轻静止缓慢滑动，不是舵机P值。'),
])
en = {
 'kt':'Torque / back-EMF constant','error_gain_ratio':'Position error gain ratio','R':'Equivalent resistance',
 'armature':'Reflected rotor inertia','q_offset':'Identification angle offset','command_delay':'Identification command delay',
 'friction_base':'Coulomb friction','friction_stribeck':'Stribeck friction','load_friction_motor':'Motor-load friction',
 'load_friction_external':'External-load friction','load_friction_motor_stribeck':'Motor-load Stribeck friction',
 'load_friction_external_stribeck':'External-load Stribeck friction','load_friction_motor_quad':'Quadratic motor-load friction',
 'load_friction_external_quad':'Quadratic external-load friction','dtheta_stribeck':'Stribeck transition velocity',
 'alpha':'Stribeck shape exponent','friction_viscous':'Viscous friction','max_velocity':'Internal target slew limit',
 'model':'BAM model family','actuator':'Actuator asset label'}
help_ = json.loads((ROOT/'data/baseline_official0151.json').read_text())['bam_help']
data['bam_fields']={k:{**v,'english':en[k],'usage':'来源标识' if k in ('model','actuator') else '辨识记录，当前训练未使用' if k in ('q_offset','command_delay') else '参与训练计算'} for k,v in help_.items()}
data['bam_fields']['q_offset']['explanation']='辨识台架的角度偏差；当前bam.mjlab控制链不使用此字段，也不是本机标定零点。'
data['bam_fields']['command_delay']['explanation']='辨识文件记录约6ms；当前bam.mjlab不消费该字段。实际延迟由执行器队列3～6个物理步产生，不能把两者相加。'
data['runtime_fields']=fields([
 ('implementation','实际控制实现','Loaded controller class','类名','XL330与STS3215使用不同控制律；HD1910辨识文件选用后者作为模型结构。'),
 ('error_gain','误差到PWM换算','Error-to-PWM gain','1/(raw·rad)','将固件P×角误差转换为占空比；不是动作缩放。'),
 ('max_pwm','最大PWM占空比','Maximum PWM duty','0～1','XL330模型1.0；飞特模型0.97。'),
 ('max_current','模型电流限制','Model current limit','A','XL330有1.75A限制；飞特模型没有这一限制，不代表实机无保护。'),
 ('duty_slope_per_rad','未饱和位置响应斜率','Unsaturated duty slope','1/rad','kp_fw×error_gain×error_gain_ratio；比较同样角误差下的模型PWM响应。'),
 ('electrical_damping','反电动势阻尼','Back-EMF damping','N·m·s/rad','kt²/R；还会乘kd_scale，另加黏性/干摩擦。kd_scale不是硬件D寄存器。'),
 ('compiled_force_limit_nm','编译扭矩边界','Compiled force limit','N·m','vin_range上限×kt/R；MuJoCo的毛扭矩上界，非额定/实测扭矩。'),
 ('static_motor_ceiling_nm','静止毛扭矩上界','Static motor torque ceiling','N·m','由最大电压、PWM与模型电流限制计算，未扣除摩擦，非连续扭矩。'),
 ('armature','实际转子附加惯量','Loaded armature','kg·m²','构建后的BAM读回值；与壳体/部件的刚体惯量不同。'),
 ('max_velocity','内部目标变化上限','Internal target slew limit','rad/s','飞特模型100rad/s只限制内部目标，不能当作舵机实际空载速度。'),
])

translations={
 'MCU':('主控芯片','硬件参考；不直接输入训练'),
 'Position Sensor':('位置传感器','影响量化和反馈误差，具体噪声由任务观测设置'),
 'Motor':('电机类型','硬件参考，电气响应由BAM模型表示'),
 'Baud Rate':('通信波特率','真实链路时延参考；训练通过队列延迟模拟'),
 'Control Algorithm':('控制算法','实物PID能力；本版BAM模型用位置P和反电动势'),
 'Resolution':('编码器分辨率','实机角度单位；模型观测使用rad'),
 'Operating Modes':('工作模式','硬件模式枚举；不在训练中切换寄存器'),
 'Weight':('单颗质量','15颗替换重量已进入机器人刚体质量'),
 'Dimensions (W x H x D)':('外形尺寸（宽×高×深）','影响装配和碰撞外形，不会凭尺寸自动改MJCF'),
 'Gear Ratio':('减速比','由辨识后的输出侧kt、R、惯量等综合表示，不能再乘一次'),
 'Stall Torque':('堵转扭矩','极限工况对照；不是连续工作扭矩，也不直接写入BAM'),
 'No Load Speed':('空载转速','用于核对速度量级，不等于带载速度或内部目标变化速度'),
 'Operating Temperature':('工作温度','硬件工作条件；当前未模拟热模型'),
 'Input Voltage':('输入电压','厂家允许范围；训练仿真电压单独列出'),
 'Command Signal':('指令信号','通信协议参考，不直接参与动力学'),
 'Physical Connection':('物理通信接口','TTL半双工多机总线；不等于供电电压'),
 'ID':('总线地址容量','实机寻址，训练按关节名映射'),
 'Feedback':('反馈量','位置/速度用于策略观测，其他用于实机诊断'),
 'Case Material':('外壳材料','影响质量/碰撞接触，当前无外壳弹性模型'),
 'Gear Material':('齿轮材料','影响传动摩擦/齿隙/强度；不是单一BAM字段'),
 'Standby Current':('待机电流','供电参考，当前未做整机静态功耗模型'),
}
specs=[]
for tr in soup.select('table')[0].select('tr')[1:]:
    name,value=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
    zh,usage=translations[name]
    specs.append({'key':name,'label':zh+' / '+name,'title':zh,'english':name,'value':value,'unit':'见数值',
                  'hd1910':'23 g（用户实测）' if name=='Weight' else '4096 counts/rev（当前适配约定）' if name=='Resolution' else '待对应型号厂家资料 / 实测',
                  'usage':usage})
extra=[
 ('position_unit','角度最小单位','Position increment',360/4096,'°/count','4096计数的精确换算；手册约0.088°。','同一4096计数换算；零点/方向单独标定'),
 ('connector','接插件','Connector','JST EHR-03 / B3B-EH-A / SEH-001T-P0.6','型号','针1=GND，2=VDD，3=DATA；官方线规21AWG。','本机线材/插头需按实物核对'),
 ('protocol','协议','Protocol','DYNAMIXEL 2.0；另支持SBUS/iBUS/RC PWM','协议','非PWM引脚角度模型；训练不传实际总线报文。','飞特协议翻译层，不可直接互写控制表'),
 ('estimated_continuous','厂家商店估算连续扭矩','Estimated continuous torque',.10,'N·m @5V','ROBOTIS美国商店按堵转扭矩20%估算，不是实测热额定曲线。','未提供对应可比数据'),
 ('backlash','机械回差','Backlash','厂家商店标为 NA','°','未给量化值；本中控普通脚任务未启用独立backlash关节。','未实测'),
 ('axial_load','轴向负载限制','Axial load limit','厂家商店标为 NA','N','未给量化值。','未实测'),
 ('radial_load','径向负载限制','Radial load limit','厂家商店标为 NA','N','未给量化值。','未实测'),
]
for k,zh,en_,v,u,use,hd in extra:specs.append(dict(key=k,title=zh,english=en_,label=zh+' / '+en_,value=v,unit=u,usage=use,hd1910=hd))
data['specifications']=specs
hd_spec={
 'Position Sensor':'12-bit磁编码（C001厂家规格）','Motor':'空心杯 / Coreless',
 'Baud Rate':'38400bps～1Mbps；厂规默认1Mbps','Control Algorithm':'PID；模式4使用位置PD',
 'Resolution':'4096 counts/rev；约0.088°/count','Operating Modes':'0角度限力 / 1恒速 / 2恒流 / 3PWM / 4位置PD（厂规默认）',
 'Weight':'本机23g；厂规21±2g','Dimensions (W x H x D)':'厂规34×20×23mm；轴向定义需按图纸核对',
 'Gear Ratio':'320:1','Stall Torque':'9 / 12 / 15 kgf·cm @4.8 / 6 / 7.4V',
 'No Load Speed':'73 / 92 / 113 rpm @4.8 / 6 / 7.4V',
 'Operating Temperature':'−20～60°C','Input Voltage':'4～8.4V',
 'Command Signal':'数字数据包','Physical Connection':'TTL半双工；8N1',
 'ID':'0～253；厂规默认1','Feedback':'电压、负载、电流、速度、温度、位置',
 'Case Material':'PA66+GF43%','Gear Material':'金属齿轮','Standby Current':'20mA',
 'connector':'AMP2.0-3P；厂规1=Signal / 2=Vcc / 3=GND；15±0.5cm线',
 'backlash':'厂规≤0.5°；本机未实测',
 'estimated_continuous':'厂规额定负载3kgf·cm≈0.2942N·m @6V；与XL330商店估算法不同',
}
for spec in specs:
    if spec['key'] in hd_spec:spec['hd1910']=hd_spec[spec['key']]
data['hd1910_manufacturer']={
 'model':'HD-1910-C001','edition':'A/0 · 2026-09-07',
 'source_url':'https://github.com/JoyandAI/OpenMicroDuck/blob/main/hardware_spec/servo/HD-1910-C001%E4%B8%B2%E5%9E%8B%E8%A7%84%E6%A0%BC%E4%B9%A6-20260907.pdf',
 'note':'飞特厂家原始PDF的社区存档；规格不代表本机固件/寄存器已核验。质量沿用用户23g，所有厂规数值仅作对照，不覆盖训练。',
 'performance':[{'voltage_v':v,'stall_torque_nm':torque*.0980665,'stall_current_a':current,'no_load_speed_rpm':rpm,
                 'rated_torque_nm':rated*.0980665,'rated_current_a':rated_current,'no_load_current_a_max':idle,
                 'no_load_speed_rad_s':rpm*2*3.141592653589793/60,'no_load_s_per_60deg':10/rpm}
                for v,torque,current,rpm,rated,rated_current,idle in [(4.8,9,1.2,73,2.2,.5,.160),(6,12,1.6,92,3,.690,.180),(7.4,15,2,113,3.7,.9,.210)]],
}
for p in data['performance']:
    p['no_load_speed_rad_s']=p['no_load_speed_rpm']*2*3.141592653589793/60
    p['no_load_s_per_60deg']=10/p['no_load_speed_rpm']
data['inertia']={
 'source_url':'https://www.robotis.com/service/download.php?no=2136',
 'download_url':'https://www.dropbox.com/s/88jbmlyv8v1o73t/XL330%2CXC330%20Moment%20of%20Inertia.pdf?dl=1',
 'released':'2023-02','mass_g':18.0,'com_mm':[-.29100243,-9.2403727,-13.121748],
 'tensor_g_mm2':[[2555.5250,-20.247808,-11.076849],[-20.247808,1271.1372,-229.79973],[-11.076849,-229.79973,2271.2629]],
 'unit_conversion':'1 g·mm² = 1e-9 kg·m²',
 'note':'厂家标注仅供参考；坐标方向与原点见PDF的轴图。重心、惯量必须旋转/平移到机器人刚体系后使用；不是BAM armature，不能直接替换。飞特对应数据待实测。',
}

register_names=['型号编号','型号信息','固件版本','总线ID','波特率编号','回包等待时间','驱动模式','工作模式','影子ID','协议类型','零位偏移','运动判断阈值','温度上限','电压上限','电压下限','PWM上限','电流上限','速度上限','位置上限','位置下限','启动配置','PWM爬升斜率','卸力条件',
 '扭矩使能','状态灯','状态包返回等级','注册写待执行标记','硬件错误状态','速度积分增益','速度比例增益','位置微分增益','位置积分增益','位置比例增益','二阶前馈增益','一阶前馈增益','总线看门狗','目标PWM','目标电流','目标速度','轨迹加速度','轨迹速度','目标位置','实时时钟','运动标记','运动状态','反馈PWM','反馈电流','反馈速度','反馈位置','轨迹速度状态','轨迹位置状态','输入电压反馈','温度反馈','备份就绪']
registers=[]
for index,area in [(3,'EEPROM'),(4,'RAM')]:
    for tr in soup.select('table')[index].select('tr')[1:]:
        c=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
        if len(c)!=7 or not c[0].isdigit() or int(c[0])>=168:continue
        a,size,name,access,initial,range_,unit=c
        val=None if initial=='-' else int(initial.replace(',',''))
        registers.append(dict(address=int(a),size_bytes=int(size),area=area,english=name,
                              default=val,range=range_,unit=unit,access=access))
assert len(register_names)==len(registers),(len(register_names),len(registers))
for r,zh in zip(registers,register_names):
    r.update(title=zh,label=zh+' / '+r['english'],usage='实物寄存器参考；当前训练不逐个仿真该寄存器',hd1910='协议/单位不同；不可直接抄写')
special={
 9:'厂家初值500μs回包等待；不同于训练中的总指令延迟15～30ms。',
 13:'2=DYNAMIXEL 2.0；20=SBUS、21=iBUS、22=RC PWM（固件支持依版本）。',
 20:'编码器零位偏移；不能把BAM台架q_offset填到这里。',
 36:'885约为100%占空比；训练类的max_pwm=1.0。',
 38:'1750对应1.75A；XL330 BAM类也建模了电流限制，飞特模型没有同一限制。',
 44:'控制表写范围0～2047，但详细说明写0～1023；保留厂家不一致，需按实际固件核对。',
 80:'厂家内部位置D=原始值/16；本版BAM没有该D寄存器闭环，kd_scale只缩放反电动势。',
 82:'厂家内部位置I=原始值/65536；当前BAM无积分控制。',
 84:'厂家说明内部P=原始值/128；BAM作者实测XL330使用除256再除PWM上限的换算，不能混用。训练P=200，厂家初值400。',
 76:'厂家内部速度I=原始值/65536；不参与当前位置BAM控制律。',
 78:'厂家内部速度P=原始值/128；不参与当前位置BAM控制律。',
 88:'厂家二阶前馈=原始值/4；当前BAM无该前馈。',
 90:'厂家一阶前馈=原始值/4；当前BAM无该前馈。',
 98:'0禁用；1～127按20ms计时；-1表示通信超时错误。',
 100:'单位约0.113%/count；PWM模式为指令，其他模式作限制。',
 108:'速度型：214.577rpm²/count；时间型：ms。0不施加该轨迹加速限制；物理加速度仍有限。',
 112:'速度型：0.229rpm/count；时间型：ms。0不施加该轨迹限制；不是电机物理速度无限。',
 124:'单位约0.113%/count。',
 126:'1mA/count仅适用XL330，飞特电流换算仍未确认。',
 128:'0.229rpm/count约0.023981rad/s/count；不能直接套到飞特。',
 132:'4096counts/rev；多圈/断电/模式切换行为应按该工作模式处理。',
}
for r in registers:
    if r['address'] in special:r['usage']=special[r['address']]
for i in range(1,29):
    for a,size,name,zh,default,range_,unit in [(168+2*(i-1),2,'Indirect Address','间接地址映射',223+i,'64～251','地址'),(223+i,1,'Indirect Data','间接数据字节',0,'0～255','byte')]:
        registers.append(dict(address=a,size_bytes=size,area='RAM',title=zh+' '+str(i),english=name+' '+str(i),label=zh+' '+str(i)+' / '+name+' '+str(i),default=default,range=range_,unit=unit,access='RW',hd1910='无相同地址映射',usage='V53及以后28组映射；较早固件20组且数据区起点不同。不参与BAM动力学。'))
data['registers']=sorted(registers,key=lambda r:r['address'])
data['register_version_note']='完整EEPROM/RAM控制表；已展开28组间接地址及数据。V53以前只有20组：地址168～207、数据208～227。表内初值不是Microduck的实机读回。'
data['resources']=[
 {'title':'ROBOTIS官方型号手册 / Official model manual','url':data['manufacturer_source']},
 {'title':'厂家原始惯量PDF / Inertia reference','url':data['inertia']['download_url']},
 {'title':'外形尺寸PDF / Dimension drawing','url':'https://www.robotis.com/service/download.php?no=1986'},
 {'title':'ROBOTIS美国商店 / Manufacturer product page','url':'https://robotis.us/products/dynamixel-xl330-m288-t'},
]
data['notes']=[
 '范围：Microduck冻结BAM基线对应XL330-M288；M077减速比和速度不同，不混入本表。',
 '厂家初值、Microduck官方训练值、飞特本页计划值分开显示；不自动把XL330参数写入飞特。',
 '当前飞特23g/颗为用户实测；扭矩、电阻、摩擦等BAM值是来源仓库的辨识资产，不是对这15颗舵机重新测出的结果。',
 'BAM q_offset和command_delay在当前mjlab训练桥接中不参与计算；指令延迟由队列设置。',
 '制造商页面存在局部不一致：波特率总表最高4Mbps但通用说明出现4.5Mbps；速度上限总表与详情范围不同；电压通用详情出现其他系列范围。物理电压规格仍按3.7～6V，不照通用段落给XL330加高压。',
]
data['official_training']['parameter_file']['url']='https://github.com/Rhoban/bam/blob/62bd8ce12154340be97e06f7f41a0ca8f116d967/bam/params/xl330/m6.json'
data['source_files']={
 'training':'https://github.com/pollen-robotics/microduck_rl/blob/8d0db74916a4f833d1d9b95d6a1d7f4d13b9d5ec/src/mjlab_microduck/robot/microduck_constants.py',
 'xl330_controller':'https://github.com/Rhoban/bam/blob/62bd8ce12154340be97e06f7f41a0ca8f116d967/bam/dynamixel/actuator.py',
 'feetech_controller':'https://github.com/Rhoban/bam/blob/62bd8ce12154340be97e06f7f41a0ca8f116d967/bam/feetech/actuator.py',
 'mjlab_bridge':'https://github.com/Rhoban/bam/blob/62bd8ce12154340be97e06f7f41a0ca8f116d967/bam/mjlab.py',
}
PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Reference facts:',len(data['specifications']),'specifications,',len(data['registers']),'registers,',len(data['bam_fields']),'BAM fields,',len(data['actuator_fields']),'actuator fields')
