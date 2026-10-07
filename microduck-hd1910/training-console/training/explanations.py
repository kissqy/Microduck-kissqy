"""Chinese field help; annotations never alter training values or source order."""
from .official_spec import RUNTIME_JOINTS

# label | meaning | unit. Context below makes repeated fields specific to their term.
TEXT = '''
target_height_min|最低目标重心高度 / Minimum target CoM height|高度范围奖励的下限；读取躯干根刚体相对地形原点的高度，低于本值会受罚。|m
target_height_max|最高目标重心高度 / Maximum target CoM height|高度范围奖励的上限；高于本值会受罚，处在上下限之间得到正奖励。|m
action_name|动作项名称 / Action term name|选择要读取实际处理后目标角的动作项；超限奖励使用它检查目标是否超过关节硬限位。|名称
overshoot|超硬限位容许偏移 / Overshoot allowance|超限惩罚只计超过硬限位再加此容许量的部分；给低P增益舵机留出达到边界姿态的目标余量。|rad
vel_scale|滑轮转速奖励饱和速度 / Wheel speed saturation|将速度除以轮半径换算滑轮角速度，在此线速度量级通过tanh逐渐饱和，避免奖励无止境加速。|m/s
vel_gate_ref|前进速度门控基准 / Forward speed gate|抬脚或单脚支撑奖励随实际前进速度从0线性增长到1；0关闭此门控，避免原地抬脚刷分。|m/s
vel_ref|滑行奖励速度基准 / Glide speed reference|前进速度奖励的参考尺度；单脚滑行奖励使用速度门控并要求腿部安静，前进速度奖励使用tanh饱和，具体看所属奖励项。|m/s
target_pitch|目标前倾角 / Target forward lean|前进轮滑姿态奖励的最佳前倾角；围绕此角度用指数函数计算奖励。|rad
head_alpha|头颈目标滤波 α / Head target EMA alpha|4个头颈关节：新目标乘α＋上一帧滤波目标乘(1−α)。每个策略控制周期更新一次；1为直通，不是动作幅度缩放。|系数
legs_alpha|腿部目标滤波 α / Leg target EMA alpha|10个腿部关节：新目标乘α＋上一帧滤波目标乘(1−α)。不作用于嘴巴或被动关节；上一帧动作观测仍为策略原始输出。|系数
filter_version|动作滤波版本 / Action filter version|本地训练适配器的动作滤波实现版本；每个环境复位后首个目标直通，后续按50Hz独立保存滤波历史。|版本
decimation|每次动作对应的物理步数|策略输出一次动作后，物理引擎推进多少小步；与timestep共同决定控制频率。|物理步
num_envs|并行鸭子数量|同时采样的仿真环境数量；更多环境通常更占显存。中控启动专栏的环境数会覆盖源码初值。|个
env_spacing|仿真环境间距|在场景中排开各只仿真鸭子的距离，不是实机尺寸。|m
sort_actuators|执行器是否重新排序|决定是否对执行器名称排序；改变顺序可能改变动作向量与关节的对应关系。|开关
spec_fn|模型构建入口|用于生成MuJoCo模型的程序函数；这是来源记录，不是要填写的实测值。|函数
articulation|关节驱动配置|此对象是否配置关节和执行器；地形的null表示没有驱动关节。|结构
name|对象名称|供其他配置引用这个对象的名字；改名后所有引用必须对应。|名称
body|挂载刚体|对象附着的刚体名称；world表示固定在世界坐标。|名称
target|跟踪目标|灯光或相机需要跟踪的目标；null表示没有指定跟踪对象。|名称
type|对象类型|选择这一对象的工作类型，例如定向光、二维纹理或站点坐标。|枚举
castshadow|投射阴影|是否在画面中生成阴影；这是显示设置。|开关
dir|照射方向|光线的方向向量[x,y,z]；决定画面亮暗方向。|向量
cutoff|聚光灯截角|聚光锥的截止角度；只在相应灯光模式下影响显示。|度
exponent|灯光衰减指数|控制聚光灯从中心到边缘变暗的方式。|系数
cameras|附加相机|此对象附带的相机列表；空列表表示没有额外相机。|列表
builtin|内置纹理样式|选择棋盘等程序生成的纹理样式，不是地面物理摩擦。|枚举
rgb1|纹理第一种颜色|红、绿、蓝三个通道，通常每项0到1。|RGB
rgb2|纹理第二种颜色|与第一种颜色交替生成地面图案。|RGB
mark|纹理标记样式|给纹理加边框或标记，仅改变显示。|枚举
markrgb|标记颜色|纹理标记使用的红、绿、蓝颜色。|RGB
rgba|材质颜色与透明度|依次为红、绿、蓝、透明度；最后一项1表示不透明。|RGBA
texuniform|纹理按统一尺度铺设|决定纹理是否采用统一映射尺度，仅影响外观。|开关
texrepeat|纹理重复次数|横向和纵向铺贴纹理的次数。|倍
reflectance|材质反射强度|控制画面反射效果，不是物理弹性或摩擦。|系数
texture|使用的纹理|引用已定义的纹理名称。|名称
geom_names_expr|匹配的几何体|用名称或正则表达式选中要应用材质/碰撞设置的几何体。|匹配规则
collisions|碰撞覆盖列表|为空时不额外覆盖该对象的碰撞设置；具体碰撞仍看模型和其他配置。|列表
terrain_type|地形类别|plane为平面；换地形会改变训练任务的接触环境。|枚举
terrain_generator|地形生成器|用于生成复杂地形的配置；平面任务的null表示不使用生成器。|结构
max_init_terrain_level|初始地形难度上限|限制程序生成地形的起始难度；平面任务不靠它调难度。|等级
target_names_expr|执行器驱动对象|按名称或正则表达式选择关节；排除passive_前缀表示不驱动被动关节。|匹配规则
transmission_type|执行器传动方式|joint表示控制关节，也可由框架支持其他传动对象；行走合同按关节驱动。|枚举
armature|折算到关节的转子惯量|电机/传动系统额外的转动惯量，影响加减速；不是整段骨架的刚体惯量。BAM也可能写入辨识值。|kg·m²
frictionloss|关节干摩擦|与速度大小无关、阻碍关节运动的摩擦力矩；BAM还计算动态摩擦。|N·m
viscous_damping|关节被动黏性阻尼|随角速度增大的阻力系数；不能与舵机固件D寄存器直接等同。|N·m·s/rad
delay_hold_prob|保留上次延迟的概率|重新采样延迟时，以这个概率继续使用上次延迟；0表示不额外保留。|0到1
delay_per_env_phase|错开延迟刷新时刻|让不同仿真环境在不同步刷新延迟，避免所有鸭子同步变化。|开关
delay_per_env|每个环境独立延迟|true表示每只仿真鸭子独立抽取延迟，false表示共享延迟。|开关
motor_name|内置电机名称|按预置名称选择电机；本基线使用json_path时，null不表示电机型号未知。|名称
model|BAM模型系列|m6等选择BAM摩擦/电机计算形式；使用完整JSON参数文件时可由文件提供，因此可为null。|名称
json_path|BAM辨识参数文件|加载kt、电阻、摩擦等辨识值的JSON路径；真实数值另列在舵机模型页。|文件路径
vin|固定仿真电压|不使用电压范围时的固定输入电压；此处null可由vin_range提供电压，不是未知电压。|V
kp_fw|仿真固件P增益|BAM模型模拟的位置环P设置；上游值不等于本机已调好的寄存器，也不是SI刚度。|固件原始增益
vin_range|仿真供电电压范围|每个环境在此范围抽取电压，用于模拟供电差异；不是机器已测得的最低最高电压。|V
vin_drop_gain_range|负载压降系数范围|模拟电压随所有关节力矩绝对值之和下降的系数范围；越大压降越明显。|V/(N·m)
vin_min|仿真压降下限|负载压降模型不会把电压降到低于此值；不能据此认为实机不会掉到更低。|V
stiff_frictionloss|增强静摩擦约束刚度|启用时调硬关节摩擦约束，减轻MuJoCo Warp中静止关节缓慢滑动的问题；关闭则保留较软的默认约束。|开关
soft_joint_pos_limit_factor|软关节限位比例|在硬限位范围内缩小出软限位，供关节越界惩罚等使用；不是写入舵机机械限位。|比例
lights|附加灯光|附着到该对象的额外灯光列表；空列表表示没有。|列表
textures|附加纹理|该对象额外定义的图案资源；不改变质量或摩擦。|列表
materials|附加材质|该对象额外定义的视觉材质；不代表物理材料密度。|列表
contype|碰撞类型位掩码|与对方conaffinity按位匹配来决定能否碰撞；这是程序分组，不是摩擦大小。|整数位掩码
conaffinity|允许碰撞的分组|与对方contype共同决定碰撞是否启用；不能简单按数值大小理解。|整数位掩码
condim|接触约束维数|1仅法向接触；3加入切向滑动摩擦；更高维还能包含扭转/滚动摩擦。|维数
priority|接触参数优先级|两个几何体接触时，影响哪一方的接触参数优先使用。|整数
friction|接触摩擦系数|控制接触时抗滑等摩擦；具体分量和是否参与求解由condim决定。|系数
solref|接触求解参考参数|控制接触响应的软硬与阻尼等；null保留模型设置，不是缺少实测。|参数对
solimp|接触约束阻抗曲线|定义接触约束随穿透/距离变化的数值响应；不是舵机电气阻抗。|参数组
margin|接触检测边界余量|让接近的几何体在完全接触前进入接触候选计算。|m
gap|非激活接触间隔|与margin一起控制记录接触和激活约束之间的间隔。|m
solmix|接触参数混合权重|接触双方参数需要混合时使用的相对权重。|系数
disable_other_geoms|关闭未选中的碰撞体|只保留选中的碰撞几何，避免视觉网格也参与接触计算。|开关
pattern|目标匹配规则|用名称或正则选取传感器需要观察的对象，不是实测数值。|匹配规则
entity|所属场景实体|例如robot；null表示不把匹配局限到一个指定实体。|名称
exclude|排除对象|匹配后再排除这些名字；空列表表示不额外排除。|列表
fields|接触传感器输出|found表示是否接触，force表示接触力等；选择实际需要的数据。|字段列表
num_slots|每个对象保留的接触槽|限制每个主要对象保留多少个接触结果；不等于足底数量。|个
secondary_policy|多个接触目标的处理|first选第一个匹配目标，any不限定单个目标，error遇到多个时报错。|枚举
track_air_time|记录离地时间|累计脚离地和接触的持续时间，供抬脚奖励/观测使用。|开关
global_frame|使用世界坐标的接触量|切换接触向量的表达坐标；false不直接等同于世界坐标。|开关
debug|调试输出|启用这个组件的辅助调试信息，不是训练目标。|开关
radius|射线采样圆半径|在足底附近多大半径的环上采样地面高度。|m
num_samples|环形采样点数|每个采样环发出多少条射线；更多点会增加计算量。|个
include_center|加入中心射线|除环上采样点外，再测中心点的地面距离。|开关
direction|射线方向|通常[0,0,-1]向下测距；它是仿真射线方向，不是舵机direction。|向量
ray_alignment|射线坐标对齐方式|决定射线方向如何跟随机器人姿态；yaw只跟随偏航方向。|枚举
max_distance|射线最大测距|超过这个距离仍未碰到物体则记作未命中。|m
exclude_parent_body|忽略自身挂载刚体|避免射线先撞到自身所在的刚体。|开关
include_geom_groups|参与射线检测的几何组|只检测这些显示/几何分组；不同于contype碰撞位掩码。|组编号
hit_color|射线命中颜色|仅在调试显示中区分命中射线。|RGBA
miss_color|射线未命中颜色|仅在调试显示中区分没有命中的射线。|RGBA
hit_sphere_color|命中点颜色|地面采样命中标记的显示颜色。|RGBA
hit_sphere_radius|命中点显示半径|调试标记的显示大小，不是足底尺寸。|显示尺度
show_rays|显示射线|只控制调试画面是否画射线。|开关
show_normals|显示表面法线|只控制是否画出命中表面的方向标记。|开关
normal_color|法线颜色|调试方向标记的显示颜色。|RGBA
normal_length|法线显示长度|调试法线标记的长度尺度，不是机器人尺寸。|显示尺度
reduction|射线结果汇总方式|min取最近命中距离，供足底离地高度计算。|枚举
extent|场景可视范围参考|MuJoCo场景尺度参考，影响相机/可视化等默认尺度。|m
max_angle_deg|模拟IMU安装误差|训练中允许模拟的最大传感器轴线偏转角；不是当前IMU的标定角。|度
_tensor_cache|程序内部张量缓存|框架为计算保存的缓存字典；空字典正常，不需要用户填写。|内部缓存
n_min|噪声下界|在原始信号上施加的随机噪声最小值；单位与该观测相同。|同观测
n_max|噪声上界|在原始信号上施加的随机噪声最大值；范围越宽模拟测量误差越大。|同观测
clip|数值裁剪区间|把超出上下界的数值截到边界；null表示这里不额外裁剪。|同被处理量
scale|数值缩放系数|将此处数值乘上系数；1保持幅度，null表示不额外缩放。|倍
flatten_history_dim|展开历史帧|把多帧历史拼成一维输入；没有历史帧时不会凭空增加输入。|开关
preserve_order|保留名称指定顺序|true按指定名称顺序取对象，false用模型解析顺序；观测/动作顺序需保持一致。|开关
biased|读取带编码器偏差的角度|true让这个关节位置观测包含仿真编码器偏差，模拟零位误差。|开关
params|函数附加参数|空字典表示直接使用该函数默认参数，不表示参数遗失。|参数字典
noise|观测噪声模型|null表示这一项没有额外噪声；不是缺少传感器数据。|结构
command_name|关联的训练指令|指定这一计算读取哪组目标指令，如twist、head_pose或body_pose。|名称
concatenate_terms|拼成一条观测向量|把各观测项按顺序拼接；关闭会改变网络输入的数据结构。|开关
concatenate_dim|拼接维度|-1表示沿最后一维拼接；属于张量组织方式。|维度编号
enable_corruption|允许施加观测噪声|训练中为增强适应性给观测加入已配置噪声；评估通常关闭。|开关
nan_policy|异常数值处理|disabled不查；warn提示并清理；sanitize静默清理；error直接报错。|枚举
nan_check_per_term|逐观测项检查异常|用于定位NaN/Inf来自哪一项；还受nan_policy是否启用影响。|开关
sensor_name|引用的仿真传感器|计算这项观测/奖励时取哪个传感器结果；不是总线ID。|名称
entity_name|引用的机器人实体|选择场景中哪一个实体作为计算或观察对象。|名称
offset|动作额外偏置|在缩放后的动作上加固定偏置；默认Home偏置还由use_default_offset控制。|rad
use_default_offset|动作围绕Home|启用后目标关节角围绕模型默认关节角生成，需与实机部署Home一致。|开关
interval_range_s|事件间隔范围|interval类事件在此时间范围重新安排下次执行；其他事件为null是正常的。|s
is_global_time|事件共用计时|true使用全局事件时钟，false按环境分别计时；主要影响周期事件。|开关
min_step_count_between_reset|重置事件最小步间隔|避免重置类事件在相隔太少步时重复执行；0不额外限制。|控制步
position_range|重置时关节角偏移|在Home上叠加的随机初始角度范围；[0,0]不加偏移。|rad
shared_random|所选对象共用随机值|例如让同一环境两只脚抽到相同摩擦系数；不同环境仍可不同。|开关
bias_range|编码器零位误差范围|模拟关节角读数的固定偏差，不改变真实机械关节角。|rad
alpha_range|质量惯量扰动的对数范围|在伪惯量参数化中施加对数尺度扰动；不是直接±多少克。|对数参数
scale_range|模型参数随机缩放|在给定比例范围缩放原参数；[0.9,1.1]即原值的90%到110%。|倍
seed|随机种子|控制随机采样的起点；同种子有助于复现，但不同GPU/计算环境仍可能有差异。|整数
nconmax|接触缓冲容量|为物理接触分配的容量上限；不足可能溢出，过大增加显存。|接触数
njmax|约束缓冲容量|物理求解器用于关节/接触等约束的存储容量，不是关节个数。|约束数
ls_parallel|并行线搜索|求解器使用并行线搜索实现；影响速度和内存，不是PPO搜索。|开关
contact_sensor_maxmatch|接触传感器匹配容量|每类传感器可匹配的接触对象容量，避免运行时分配不足。|个
timestep|物理仿真小步时长|每推进一次物理引擎经过的模拟时间；0.005秒对应200Hz。|s
integrator|物理积分算法|implicitfast等决定如何由力/速度更新状态，影响数值稳定性和速度。|枚举
impratio|摩擦与法向阻抗比|接触求解时摩擦方向相对法向的阻抗比例，不是摩擦系数本身。|比例
cone|接触摩擦锥形式|pyramidal使用多面体近似；elliptic使用椭圆摩擦锥模型。|枚举
jacobian|约束雅可比存储|auto让引擎选择稀疏/稠密等内部表示，不是训练网络矩阵。|枚举
solver|物理约束求解算法|newton等用于求解接触和约束，不是PPO优化器。|枚举
iterations|物理求解迭代上限|每个物理小步允许求解器迭代多少次；不是训练轮数。|次/物理步
tolerance|物理解算收敛容差|求解误差小到该阈值可提前结束；更小通常要求更严格。|数值容差
ls_iterations|物理线搜索迭代上限|求解器每次线搜索允许的最大尝试次数。|次
ls_tolerance|物理线搜索容差|线搜索判断是否足够收敛的阈值。|数值容差
ccd_iterations|凸碰撞检测迭代上限|用于凸体碰撞检测的最大迭代次数；不是PPO训练步数。|次
gravity|世界重力加速度|[0,0,-9.81]表示世界Z轴向下的标准近似重力。|m/s²
disableflags|禁用的物理功能|显式关闭的引擎功能列表；空列表不额外关闭。|列表
enableflags|额外启用的物理功能|显式开启的引擎功能列表；空列表沿用默认。|列表
enabled|启用异常状态捕获|允许记录数值异常发生前的仿真状态，便于排错；不是启用训练。|开关
buffer_size|异常捕获缓存长度|保留多少步历史仿真状态以便诊断数值异常。|步
output_dir|异常状态保存目录|出现数值异常时转储文件的路径。|文件夹
max_envs_to_dump|异常转储环境数上限|最多保存多少个环境的异常现场，防止生成过多文件。|个
lookat|相机观察点|画面相机对准的三维坐标，不改变物理模型位置。|m
distance|相机距离|相机离观察点的距离，只影响画面。|m
fovy|相机垂直视场角|控制画面视野宽窄；null使用引擎默认相机设置。|度
elevation|相机俯仰角|从什么高度方向观察机器人，不是机身姿态。|度
azimuth|相机方位角|从哪个水平方向观察机器人，不是机器人转向命令。|度
origin_type|相机参考原点模式|决定观察点相对于世界/环境/机器人计算的方式；这是程序枚举记录。|枚举
body_name|跟随的刚体|相机围绕哪个刚体观察，例如躯干；不是待测传感器。|名称
env_idx|显示的环境编号|在多个仿真环境中主要看哪一个，编号从0开始。|编号
max_extra_envs|额外显示的环境数|除主要环境外，最多同时画出多少只鸭子。|个
enable_reflections|显示反射效果|仅影响渲染效果和渲染开销。|开关
enable_shadows|显示阴影效果|仅影响渲染效果和渲染开销。|开关
episode_length_s|单回合最长时间|一只鸭子这一回合最多走多久，超时后按任务规则重置。|s
walking_threshold|站立切换为行走的阈值|目标平面速度超过该值时，姿态奖励采用行走姿态宽容度。|m/s
running_threshold|行走切换为快走的阈值|目标平面速度超过该值时，姿态奖励采用快走/跑步宽容度。|m/s
threshold_min|离地时间下阈值|脚离地时间奖励使用的下界，用来限定期望步态节奏。|s
threshold_max|离地时间上阈值|脚离地时间奖励使用的上界，避免单脚长时间悬空。|s
command_threshold|启用步态项的命令阈值|目标运动量达到阈值才应用该步态项，避免静止时仍鼓励抬脚。|按函数中的命令范数
target_height|目标抬脚高度|希望摆动脚离地的高度；过高会形成夸张抬腿，过低容易擦地。|m
height_sensor_name|高度传感器引用|从哪组仿真射线结果获得脚离地高度。|名称
nominal_height|身体高度基准|身体姿态目标所使用的参考高度；不一定等于MJCF初始根节点高度。|m
xy_std|水平位置奖励宽度|身体位置跟踪误差的水平容忍尺度，越大对偏差越宽容。|m
z_std|高度奖励宽度|身体高度跟踪的容忍尺度，越大对高度偏差越宽容。|m
angle_std|姿态角奖励宽度|身体角度跟踪的容忍尺度，越大对角度偏差越宽容。|rad
tau_s|姿态偏差平滑时间常数|用于累计/平滑头部长期偏差；更长会对长期偏置更平滑地响应。|s
time_out|是否属于时间截断|true表示超时/边界等截断，可与摔倒失败采用不同的价值估计处理。|开关
limit_angle|倾倒终止角度|机身相对直立偏转超过此角度时按摔倒结束回合。|rad
sensor_names|检查的传感器列表|列出异常检测要检查哪些仿真传感器。|名称列表
resampling_time_range|重新抽取指令的间隔|每隔多少秒给该环境换一个训练目标，按范围随机抽取。|s
heading_command|启用目标朝向命令|允许用目标朝向误差计算转向命令，还要看朝向环境的分配比例。|开关
heading_control_stiffness|朝向纠偏系数|目标朝向与当前朝向的误差乘此系数，得到转向速度命令。|1/s
rel_standing_envs|站立训练环境占比|有多少比例的环境收到零速度站立命令；课程会逐步修改它。|0到1
rel_heading_envs|朝向控制环境占比|多少环境通过目标朝向生成转向命令；0表示不分配此类环境。|0到1
rel_world_envs|世界坐标命令占比|多少环境按世界坐标解释速度目标，而非机身坐标。|0到1
rel_forward_envs|只向前走的环境占比|分配给偏向纯前进命令的环境比例，用于调整训练命令分布。|0到1
init_velocity_prob|重置时带初速度的概率|以此概率让重置的鸭子从非零速度状态开始。|0到1
lin_vel_x|前后速度命令范围|负数后退，正数前进；范围是训练抽样范围。|m/s
lin_vel_y|横向速度命令范围|机身坐标中横向移动速度范围；正负方向以坐标合同为准。|m/s
ang_vel_z|转向角速度命令范围|围绕竖直轴旋转的目标速度范围。|rad/s
heading|目标朝向角范围|朝向控制环境抽取的目标航向角范围。|rad
z_offset|命令箭头显示高度|在画面中把速度箭头向上移多少；不改变机器人高度。|m
rel_turn_in_place_envs|原地转向环境占比|给一部分环境只发转向、不发平移的命令。|0到1
zero_command_prob|姿态目标归零概率|重新采样时以该概率把这一组姿态目标全部置零。|0到1
reward_name|课程修改的奖励项|指明这一课程调度要修改哪一项奖励权重。|名称
event_name|课程修改的随机事件|指明这一课程要扩大哪一个随机化事件的范围。|名称
step|课程阶段开始步数|按环境的控制步计数触发，不是PPO轮数或所有环境总样本数；24步/轮时12000步约500轮。|环境控制步
per_substep|每个物理小步统计|true按物理小步记录指标，false按控制步记录。|开关
recorders|额外记录器|附加状态记录组件；空字典表示没有添加，训练日志仍由训练器保存。|字典
is_finite_horizon|是否有限时域任务|决定回合时间上限是否本身属于任务目标，影响超时处的价值估计。|开关
auto_reset|回合结束自动复位|摔倒或超时等结束后自动开始下一回合。|开关
scale_rewards_by_dt|按控制时长缩放奖励|每步奖励乘控制步时长，减少控制频率改变带来的总奖励尺度差异。|开关
num_steps_per_env|每轮每只鸭子的采样步数|采样这么多控制步后进行一轮PPO更新；与并行环境数共同决定一批数据量。|控制步/轮
max_iterations|本次训练轮数|PPO计划执行多少轮更新；续训时按该训练器语义追加本次轮数，中控启动专栏优先。|轮
save_interval|检查点保存间隔|每隔多少轮保存一次PT，决定可恢复点和周期仿真更新频率。|轮
experiment_name|实验目录分类|训练输出按这个名称分组，不是网络参数。|文字
run_name|本次运行名称|用于区分同一实验的多次运行；中控会生成唯一运行名。|文字
logger|日志保存工具|tensorboard表示在本地写TensorBoard日志。|枚举
wandb_project|可选云日志项目|只有使用WandB日志时才有作用；当前本地TensorBoard不依赖它。|文字
wandb_tags|可选云日志标签|给WandB运行加标签；空列表正常。|列表
resume|从检查点续训|true从既有模型继续，false新建训练；中控通过选中的来源检查点控制。|开关
load_run|续训来源目录匹配|用名称/正则寻找要加载的运行；中控会锁定用户选中的具体运行。|匹配规则
load_checkpoint|续训检查点匹配|指定PT文件名或匹配规则；中控续训选择实际存在的文件。|匹配规则
clip_actions|训练包装器动作裁剪|限制策略输出幅度；null表示这个包装层不再额外裁剪，底层仍有自己的约束。|动作单位
upload_model|上传模型开关|是否由训练器自动上传模型到其配置的服务；本地训练默认关闭。|开关
class_name|使用的算法/网络类|如PPO或MLPModel，用于选择程序实现；不是需要实测的参数。|类名
hidden_dims|神经网络隐藏层宽度|列表每个数字是一层神经元数量；[512,256,128]表示三层。|每层神经元数
activation|神经网络激活函数|ELU等为网络提供非线性能力；更换会改变网络计算。|枚举
obs_normalization|归一化网络输入|按累计均值/方差缩放观测，改善训练尺度；导出会把归一化装进ONNX。|开关
cnn_cfg|图像网络配置|null表示不使用卷积图像网络；当前走路输入是数值向量。|结构
init_std|初始动作探索幅度|高斯策略的初始标准差；较大时训练初期随机动作更明显。|动作单位
std_type|探索标准差的参数形式|scalar直接学习标准差，log学习其对数；这里不是“所有动作只共用一个标准差”的意思。|枚举
rnn_type|循环记忆网络类型|null表示当前不用RNN记忆，采用前馈网络。|枚举
rnn_hidden_dim|循环网络隐藏宽度|只有开启RNN时才用到；当前rnn_type=null，不需要调整这个备用值。|神经元数
rnn_num_layers|循环网络层数|只有开启RNN时才用到；当前走路MLP不使用它。|层
distribution_cfg|输出分布设置|Actor用它产生探索动作；Critic的null表示输出价值，不采样动作分布。|结构
num_learning_epochs|每批数据重复学习次数|对本轮采到的同一批数据重复优化多少遍；不是物理步。|遍/轮
num_mini_batches|每轮数据分组数|把采样数据分成多少小批做梯度更新；影响显存和优化批量。|组
learning_rate|学习率|每次梯度更新参数的步幅；过大可能不稳定，过小学习较慢。|系数
schedule|学习率调整方式|adaptive根据策略变化程度等调整学习率；不是固定不变的0.001。|枚举
gamma|未来收益折扣|越接近1，越重视更远处的奖励；不是动作平滑系数。|0到1
lam|优势估计平滑系数|GAE中平衡估计噪声与偏差的参数，不是电机参数。|0到1
entropy_coef|探索鼓励权重|鼓励策略保留随机探索，避免太早只做单一动作。|系数
desired_kl|目标策略变化幅度|用于自适应学习率等控制，限制新旧策略差异过快增长。|KL目标
max_grad_norm|梯度范数上限|梯度过大时按比例裁小，降低单次更新突然跳变。|范数
value_loss_coef|价值网络损失权重|价值预测误差在总优化目标中的权重。|系数
use_clipped_value_loss|裁剪价值网络更新|限制价值预测相对旧预测的变化，用于稳定更新。|开关
clip_param|PPO策略更新裁剪|约束新旧动作概率比的变化范围；0.2不是关节限位20%。|系数
normalize_advantage_per_mini_batch|每小批归一化优势|决定优势估计是在每个小批内归一化还是用其他批级处理。|开关
optimizer|神经网络优化器|adam等负责更新网络权重，不是MuJoCo物理求解器。|枚举
share_cnn_encoders|共享图像编码器|Actor与Critic是否共用CNN；当前无CNN，因此此开关不影响现有MLP结构。|开关
symmetry_cfg|对称增强配置|null表示没有额外开启该接口的镜像增强，不代表机器人没有左右对称结构。|结构
'''
TEXT += '''
face_down_prob|面朝下初始化比例|控制所属复位事件抽到面朝下姿态的比例；侧躺分支存在时用于其余倒地样本；多姿态权重事件会与其他姿态权重一起归一化。不是起身成功率。|概率/相对权重
face_up_prob|面朝上初始化权重|多姿态复位事件中抽到面朝上的相对权重，与同事件其他姿态权重归一化。|相对权重
side_prob|侧躺初始化比例|倒地初始化样本中采用侧躺的比例，左右侧再随机分配。不是全体训练环境中固定的侧躺数量。|概率（0至1）
prone_prob|倒地起步比例|复位时，将本次重置环境的一部分改为倒地姿态；课程可随训练进度调整该比例。|概率（0至1）
crouch_prob|低姿态起步比例|复位时额外选取互不重叠的一部分环境，以低姿态开始；与倒地起步比例共同决定初始样本分布。|概率（0至1）
sitting_prob|坐姿初始化权重|多姿态复位时抽到坐姿的相对权重，与同事件其他姿态权重一起归一化。|相对权重
standing_prob|站姿初始化权重|多姿态复位时抽到站姿的相对权重，与同事件其他姿态权重一起归一化。|相对权重
prone_z_min|倒地初始高度下限|倒地起步时基座相对所在环境的初始化高度下限；与上限共同决定抽样区间。|m
prone_z_max|倒地初始高度上限|倒地起步时基座相对所在环境的初始化高度上限；过高会产生额外自由落体。|m
fallen_scale|倒地时的惩罚倍率|判定倒地后，动作变化或力矩变化惩罚乘以此值；站立时保持原惩罚。用于给起身动作留下活动空间。|倍
gate_tilt_above_deg|倒地倾斜判定角|身体倾斜超过此角度时启用所属倒地奖励、惩罚或结束条件；是否还包含高度条件取决于该项函数。|度
gate_z_below|倒地高度判定线|身体高度低于此值时进入所属倒地条件，与倾斜判据配合使用；不是机械关节限位。|m
fallen_tilt_deg|进入倒地状态的倾角|恢复成功奖励中，用于确认已经经历倒地的倾斜门槛。|度
release_tilt_below_deg|退出倒地状态的倾角|身体倾斜减小到此角度以内时解除所属倒地状态锁定，避免判定在边界反复跳动。|度
release_z_above|恢复高度门槛|所属恢复条件要求身体高度超过此值；需结合该函数的其他条件。|m
up_tilt_deg|成功站起的倾角上限|倾斜小于此角度并满足恢复高度条件后，计入站起判定。|度
up_z|成功站起的高度门槛|身体相对地面的高度超过此值，并满足倾斜条件后，计入站起判定。|m
min_fallen_s|计入恢复前的最短倒地时间|必须先持续倒地达到这段时间，随后站起才可计为一次有效恢复；避免普通步态抖动刷奖励。|s
max_duration_s|连续倒地允许时长|持续满足所属倒地条件超过此时间后结束并重置该环境的回合，不是停止整次训练。|s
acc_thresh|关节加速度惩罚门槛|关节加速度幅度超出此值的部分计入尖峰惩罚；不是直接限制舵机的加速度寄存器。|rad/s²
torque_thresh|堵转惩罚力矩门槛|力矩超过此值，同时关节速度低于速度门槛时计入堵转惩罚；属于训练奖励判据。|N·m
vel_thresh|堵转惩罚速度门槛|关节速度幅度低于此值且力矩较大时计入堵转惩罚。|rad/s
ceiling|高度进展奖励上限|高度超过此线后，不再通过继续抬高身体增加本项高度进展奖励。|m
max_height|起身奖励高度上限|限制所属起身进展/抬升奖励生效的高度范围，避免已经站稳后继续通过弹跳刷分。|m
param_stages|事件参数课程阶段|按训练步数分阶段更新事件参数；表内step通常是环境控制步数，不能直接当迭代轮数。|阶段表
push_stages|推倒强度课程阶段|随训练步数改变推扰速度范围；每阶段保留其明确的轴和单位。|阶段表
weight_stages|奖励权重课程阶段|按训练进度调整所属奖励或惩罚的权重。|阶段表
term_name|课程作用项名称|被课程调整的奖励、事件或其他管理器条目名称；具体对象由所属课程函数决定。|名称
threshold|判定阈值|所属函数执行判定使用的阈值；不同奖励或终止条件的量纲不同，应结合该条目的函数与配置路径查看。|按所属函数
'''

TEXT += '''
asset_cfg|作用对象选择|指定此奖励、事件或观测作用于哪个机器人以及哪些刚体、关节、站点。|对象选择
axis_weights|身体六轴跟踪权重|依次为x、y、z、roll、pitch、yaw的误差权重；0表示该轴不参与本项跟踪奖励。|系数
face_up_roll_max|仰卧初始化翻侧扰动|仰卧起步时，沿身体纵轴随机叠加的正负滚转角幅度；较大范围会包含更接近侧躺的起步姿态。|rad
gate_height_low|奖励高度门控下界|身体高度低于此线时，不施加所属站立阶段奖励/惩罚；到上界之间逐步启用。|m
gate_height_high|奖励高度门控上界|身体高度达到此线时，所属高度门控完全启用；仍需配合倾斜等其他条件。|m
gate_tilt_full_deg|倾角门控完全启用线|身体倾斜小于此角度时，所属直立阶段门控取满值。|度
gate_tilt_zero_deg|倾角门控关闭线|身体倾斜达到此角度时，所属直立阶段门控降为0，避免妨碍倒地起身。|度
height_low|高度过渡区间下界|所属高度插值或奖励门控的下界，与height_high配对决定从低姿态到高姿态的过渡区间。|m
height_high|高度过渡区间上界|所属高度插值或奖励门控的上界；具体过渡目标由所属函数决定。|m
tilt_full_deg|直立判定满权重倾角|低于此角度时，所属倾斜门控完全启用。|度
tilt_zero_deg|直立判定零权重倾角|高于此角度时，所属倾斜门控不再贡献；两条角度界限之间逐步过渡。|度
height_std|高度奖励误差尺度|高度偏离目标时奖励衰减的尺度；值越大，对高度误差越宽容。|m
pose_std|姿态奖励误差尺度|关节姿态偏离目标时奖励衰减的尺度；值越大，对关节角误差越宽容。|rad
upright_std|直立奖励误差尺度|控制直立方向误差的奖励衰减，不是IMU噪声；当前综合站立奖励将2×(qx²+qy²)除以此值的平方。|无量纲
joint_indices|参与计算的关节序号|所属函数选择的仿真关节/策略关节内部序号；具体索引集合由函数决定，不是舵机总线ID。|内部索引
kp_range|位置增益随机化范围|对仿真执行器的位置反馈增益进行抽样；当前起身配置operation=scale表示乘法缩放。不直接写实机寄存器。|取决于operation，当前为倍数
kd_range|速度增益随机化范围|对仿真执行器的速度反馈增益进行抽样；当前起身配置operation=scale表示乘法缩放。不直接写实机寄存器。|取决于operation，当前为倍数
range_stages|随机化范围课程|按训练步数逐阶段调整指定事件的抽样范围，每阶段保留自己的范围值。|阶段表
ranges|随机抽样范围|所属随机化事件使用的抽样上下界；具体量纲及加法/缩放含义由作用对象和operation决定。|按所属随机化对象
sitting_joint_noise_std|坐姿初始化关节扰动|围绕坐姿参考角加入随机关节角扰动的标准差。|rad
sitting_joint_overrides|坐姿参考关节角|覆盖默认Home的坐姿关节目标，用于生成坐姿起步样本；不改本机编码器零位。|rad
sitting_tilt_max|坐姿初始倾斜幅度|坐姿起步时，俯仰和侧倾随机扰动的正负最大角度。|rad
sitting_z_min|坐姿初始化高度下限|坐姿起步时身体相对所在环境的高度抽样下限。|m
sitting_z_max|坐姿初始化高度上限|坐姿起步时身体相对所在环境的高度抽样上限。|m
standing_z_min|站姿初始化高度下限|站姿起步时身体相对所在环境的高度抽样下限。|m
standing_z_max|站姿初始化高度上限|站姿起步时身体相对所在环境的高度抽样上限。|m
target_overrides|奖励目标关节角|指定本项姿态奖励使用的参考角；null表示使用默认Home姿态。|rad
vel_gate_command_name|速度门控指令名称|选择用于调整身体姿态奖励门控的速度指令；null表示不使用该速度指令门控。|指令名
dim|补齐观测维数|生成指定维数的零值观测，用于保持不同任务的策略输入结构一致。|维
'''

DEFS={x.split('|')[0]:tuple(x.split('|')[1:]) for x in TEXT.strip().splitlines()}
TERM={
'base_ang_vel':('机身角速度','机身绕三轴转动的速度','rad/s'), 'base_lin_vel':('机身线速度','机身在自身坐标中的移动速度','m/s'),
'projected_gravity':('投影重力','把世界重力方向表达在机器人坐标中，用来判断倾斜','无量纲'),
'joint_pos':('相对Home的关节角','各策略关节角减去其默认Home角','rad'),'joint_vel':('关节角速度','各策略关节转动的快慢','rad/s'),
'actions':('上一轮动作','上一轮策略的动作向量，供网络了解自己刚才做了什么','动作单位'),
'command':('行走指令','目标前后速度、横向速度、转向角速度','m/s、rad/s'),
'head_command':('头部姿态指令','目标头部姿态命令，供策略跟随','rad'),
'body_command':('身体姿态指令','目标身体位移与转角','m、rad'),
'foot_height':('脚离地高度','脚相对地面的高度','m'),'foot_air_time':('脚离地时间','脚连续离地的时长','s'),
'foot_contact':('脚是否着地','脚与地面有无接触','0/1'),'foot_contact_forces':('足底接触力','脚受到地面的接触力','N'),
}
REW={
 'track_linear_velocity':('平移速度跟踪','鼓励实际前后/横向速度接近目标'), 'track_angular_velocity':('转向速度跟踪','鼓励实际转向速度接近目标'),
 'upright':('保持直立','鼓励机身重力方向接近直立'), 'pose':('关节姿态约束','让关节别偏离参考姿态太多，站立/行走/快走使用不同宽容度'),
 'body_ang_vel':('抑制机身晃动','对不希望的机身转动增加惩罚'), 'angular_momentum':('抑制角动量','减少整体过大的旋转动量'),
 'dof_pos_limits':('避免关节越界','惩罚关节超出软限位'), 'action_rate_l2':('动作连续性','惩罚相邻动作的突变，让目标更平滑'),
 'air_time':('抬脚节奏','鼓励脚离地时间落入期望区间'), 'foot_clearance':('脚离地间隙','让移动的脚保持合适离地高度'),
 'foot_swing_height':('摆动脚高度','约束摆动阶段的抬脚高度'), 'foot_slip':('避免打滑','惩罚着地脚在地面上滑动'),
 'self_collisions':('避免自碰撞','惩罚机器人不同部分相撞'), 'head_pose_tracking':('头部跟随','鼓励头部跟随目标姿态'),
 'body_pose_tracking':('身体姿态跟随','鼓励身体的位置和角度接近目标'), 'head_pose_bias':('抑制头部长期偏差','减少头部相对命令持续偏在一边的情况')}
EVENT={
'set_ground_state':'倒地姿态初始化','random_prone_init':'混合倒地/低姿态初始化','topple_push':'强推扰/推倒训练','reset_base':'重置机身位置/方向','reset_robot_joints':'重置关节姿态','push_robot':'随机推扰','foot_friction':'足底摩擦随机化',
'encoder_bias':'编码器零位误差','base_com':'基座重心偏移','expand_bam_friction_fields':'展开每环境BAM摩擦数据',
'reset_action_history':'清空旧动作历史','randomize_com':'躯干重心随机化','randomize_head_com':'头部重心随机化',
'randomize_mass_inertia':'质量/惯量联合随机化','randomize_joint_friction':'电机摩擦随机化','randomize_armature':'转子惯量随机化'}
CURR={'action_rate_weight':'动作平滑惩罚课程','standing_envs':'站立占比课程','head_pose_range':'头部动作范围课程','body_pose_range':'身体姿态范围课程','com_range':'躯干重心范围课程','head_com_range':'头部重心范围课程','head_pose_bias_weight':'头部偏差惩罚课程'}
OBJ={'joint':'关节','body':'刚体','geom':'碰撞/视觉几何体','site':'模型站点','actuator':'执行器','tendon':'肌腱/耦合结构','camera':'相机','light':'灯光','material':'材质','pair':'接触对'}
JOINT={'hip_yaw':'髋偏航','hip_roll':'髋侧倾','hip_pitch':'髋俯仰','knee':'膝','ankle':'踝','neck_pitch':'颈俯仰','head_pitch':'头俯仰','head_yaw':'头偏航','head_roll':'头侧倾'}

def context(path):
 p=list(map(str,path))
 if p[:2]==['env','observations']:
  network='策略网络输入' if p[2]=='actor' else '价值网络输入（训练用）'
  return network+('／'+TERM.get(p[4],(p[4],))[0] if len(p)>4 and p[3]=='terms' else '')
 if p[:2]==['env','rewards']:return '奖励／'+REW.get(p[2],(p[2],))[0]
 if p[:2]==['env','events']:return '随机化/复位／'+EVENT.get(p[2],p[2])
 if p[:2]==['env','curriculum']:return '课程／'+CURR.get(p[2],p[2])
 if p[:2]==['env','commands']:return '指令／'+{'twist':'行走速度','head_pose':'头部姿态','body_pose':'身体姿态'}.get(p[2],p[2])
 if p[:2]==['env','terminations']:return '结束回合／'+{'time_out':'时间用尽','fell_over':'摔倒','out_of_terrain_bounds':'超出地形','nan_state':'异常数值'}.get(p[2],p[2])
 if p[:2]==['agent','actor']:return '策略网络（输出动作）'
 if p[:2]==['agent','critic']:return '价值网络（评价状态）'
 if p[:2]==['agent','algorithm']:return 'PPO学习算法'
 if p[0]=='agent':return '训练器'
 if p[:2]==['env','viewer']:return '仿真画面'
 if p[:2]==['env','sim']:return '物理引擎'
 if 'sensors' in p:return '仿真传感器第'+str(int(p[3])+1)+'组'
 if 'actuators' in p:return '机器人执行器模型'
 if 'collisions' in p:return '模型碰撞设置'
 if 'terrain' in p:return '地形/场景'
 if 'robot' in p:return '机器人模型'
 return '仿真环境'


def help_for(row):
 p=list(map(str,row['path']));s='.'.join(p);k=p[-1];v=row['value'];ctx=context(p);definition=None
 if p[:3]==['agent','algorithm','bc_cfg']:
  ctx='联合训练／双教师行为模仿'
  definition=BC_HELP.get(k)
 elif k.endswith('_names') and k[:-6] in OBJ:
  obj=OBJ[k[:-6]];definition=(obj+'名称选择',f'选定本项计算作用于哪些{obj}；支持名称/正则。null表示不按名称额外筛选，实际范围还看索引和函数。','名称/正则')
 elif k.endswith('_ids') and k[:-4] in OBJ:
  obj=OBJ[k[:-4]];definition=(obj+'内部索引',f'仿真模型里的{obj}索引，不是舵机总线ID。slice[null,null,null]表示全范围切片；名称选择仍会参与解析。','模型索引')
 elif k=='func':
  desc=TERM.get(p[4],('','读取该项数据',''))[1] if 'terms' in p else REW.get(p[2],('', '执行'+ctx))[1] if p[1]=='rewards' else '执行'+ctx+'所述操作'
  definition=('计算函数',desc+'；这里记录具体代码入口，通常保持上游绑定，不需要手填测量值。','函数')
 elif 'init_state' in p and p[-2] in ('joint_pos','joint_vel'):
  label=next((cn for en,cn in JOINT.items() if en in k),'匹配的全部关节');label=('左' if 'left_' in k else '右' if 'right_' in k else '')+label
  ispos='joint_pos' in p
  definition=(label+('默认角/Home' if ispos else '初始角速度'),('模型启动时的参考关节角，动作偏置/相对关节观测会使用它；不是编码器zero_raw。' if ispos else '复位时的关节角速度；0表示静止起步。'),'rad' if ispos else 'rad/s')
  if 'terrain' in p:definition=('地形实体的通用关节初值','这是实体框架保留的默认关节初值；当前平面地形没有驱动关节，不需要按实机Home填写。','rad' if ispos else 'rad/s')
 elif any(name in p[:-1] for name in ('sitting_joint_overrides','target_overrides','sit_overrides','tuck_overrides','crouch_pose','stand_pose')):
  joint=RUNTIME_JOINTS[int(k)] if k.isdigit() and int(k)<len(RUNTIME_JOINTS) else k
  label=('左' if joint.startswith('left_') else '右' if joint.startswith('right_') else '')+next((cn for en,cn in JOINT.items() if en in joint),joint)
  definition=(label+'参考关节角','所属初始化姿态或奖励目标指定的关节角；对应 '+joint+'，不是编码器零位或实时反馈角。','rad')
 elif len(p)>1 and p[-2] in ('std_standing','std_walking','std_running'):
  mode={'std_standing':'站立','std_walking':'行走','std_running':'快走'}[p[-2]];label=next((cn for en,cn in JOINT.items() if en in k),k)
  definition=(mode+'／'+label+'姿态宽容度','姿态奖励允许这组关节偏离Home的尺度；越大对偏差越宽容。','rad')
 elif len(p)>1 and p[-2] in ('contype','conaffinity','condim','priority','friction'):definition=DEFS[p[-2]]
 elif k in ('delay_min_lag','delay_max_lag','delay_update_period'):
  motor='actuators' in p;unit='物理步（本基线每步5ms）' if motor else '控制步（本基线每步20ms）'
  label={'delay_min_lag':'最小延迟步数','delay_max_lag':'最大延迟步数','delay_update_period':'延迟重采样周期'}[k]
  text='每隔多少步重新抽取延迟；0表示每步都允许更新。' if k=='delay_update_period' else '从最小到最大步数之间抽取延迟；最小=最大表示固定延迟。'
  definition=(label,text+('这是动作到执行器的延迟。' if motor else '这是传感器观测到网络的延迟。'),unit)
 elif k=='history_length':definition=('历史帧长度','保存最近多少帧供观测/传感器使用；0不堆叠历史。组级null表示沿用各子项设置。','帧')
 elif k=='mode':definition=('触发/匹配模式', 'startup只在初始化执行；reset在回合重置时执行；interval按时间间隔执行。' if p[1]=='events' else '灯光fixed表示固定；传感器geom/body/subtree分别按几何体、刚体或整棵子树匹配。不是HD1910的模式寄存器4。','枚举')
 elif k=='operation':definition=('叠加方式','add加到原值；scale乘原值；abs作为新值使用。结合本行所在噪声/随机化范围理解。','枚举')
 elif k in ('pos','rot','lin_vel','ang_vel','quat'):
  definition={'pos':('初始/相对位置','三维位置[x,y,z]；具体属于机器人、地形还是灯光见所属模块。','m'),'rot':('初始旋转四元数','按[w,x,y,z]定义朝向；[1,0,0,0]是零旋转。','四元数'),'quat':('旋转四元数','按[w,x,y,z]记录相对朝向。','四元数'),'lin_vel':('初始线速度','初始平移速度[x,y,z]；全0表示静止。','m/s'),'ang_vel':('初始角速度','初始绕三轴转动的速度；全0表示不自转。','rad/s')}[k]
 elif k in ('width','height'):definition=('图像'+('宽度' if k=='width' else '高度'),'纹理分辨率或默认渲染图像尺寸，只影响画面；不是机器人长宽高。','像素')
 elif k=='debug_vis':definition=('显示辅助图形','是否画出命令箭头/传感器等调试图形；不改变命令数值或真实测量。','开关')
 elif k=='reduce':definition=('结果汇总方式','接触传感器netforce合成接触力、none不归并；指标mean则取平均。由本行所属组件决定。','枚举')
 elif k=='weight':
  term=p[2];title=REW.get(term,(CURR.get(term,term),''))[0]
  definition=(title+'权重','放大或缩小这一奖励/惩罚在总奖励中的贡献；通常负值用于惩罚、0暂不贡献。若有课程表，后续值由课程改写。','系数')
 elif k=='std':
  unit={'track_linear_velocity':'m/s','track_angular_velocity':'rad/s','head_pose_tracking':'rad','upright':'重力方向误差尺度'}.get(p[2],'误差尺度')
  definition=('奖励误差宽容度','控制跟踪误差增长时奖励下降的快慢；越大越宽容。不是传感器噪声，也不是动作探索标准差。',unit)
 elif k in ('ranges','range'):
  if 'head_pose' in p or 'head_pose_range' in p:definition=('头部目标范围','四项依次为颈俯仰、头俯仰、头偏航、头侧倾，相对Home的角度增量；每项[下限,上限]，不是总线机械限位。','rad')
  elif 'body_pose' in p or 'body_pose_range' in p:definition=('身体目标范围','六项依次为x/y/z位移、roll/pitch/yaw转角；每项[下限,上限]。','前三项m，后三项rad')
  elif any(x in p for x in ('randomize_com','randomize_head_com','base_com','com_range','head_com_range')):definition=('重心扰动范围','围绕模型原重心抽取偏移；单个范围值用于课程设定正负对称范围，不是实测重心。','m')
  elif 'foot_friction' in p:definition=('足底摩擦抽样范围','每次按事件安排，从上下界间抽取摩擦系数，用来覆盖不同地面。','摩擦系数')
  elif 'randomize_armature' in p:definition=('转子惯量缩放范围','对原关节armature进行随机倍数缩放。','倍')
 elif k in ('x','y','z','yaw','0','1','2'):
  axis={'0':'x','1':'y','2':'z'}.get(k,k)
  definition=(axis+'方向抽样范围','对应随机复位/推扰/重心偏移的上下界；只改变所属事件选择的对象。',('rad/s' if k=='yaw' else 'm/s') if 'velocity_range' in p else 'rad' if k=='yaw' else 'm')
 elif k=='velocity_range':definition=('复位速度范围','关节复位时为角速度范围；机身的空字典表示未指定额外随机速度轴范围。','rad/s（关节）或m/s、rad/s（机身）')
 elif p[:2]==['agent','obs_groups']:definition=(('策略' if k=='actor' else '价值')+'网络输入组','选择网络读取哪一组观测；actor用于生成动作，critic主要用于训练评价。','观测组名')
 if definition is None:definition=DEFS.get(k)
 if definition is None:return missing_help(row,ctx)
 title,text,unit=definition
 if p[:2]==['env','observations'] and len(p)>4 and p[3]=='terms' and k in ('n_min','n_max','clip'):
  unit=TERM.get(p[4],('','','按所属观测量'))[2]
 if v is None:
  if k in ('armature','frictionloss','viscous_damping','solref','solimp','margin','gap','solmix'):
   text+=' 本项null表示不在此层单独覆盖，沿用模型/执行器构建时的值。'
  elif k=='seed':text+=' 环境层null可由训练器agent.seed赋值；不是要求你补一个未知种子。'
  elif k=='spec_fn':text+=' null表示未指定额外构建函数，使用框架默认场景。'
  elif k.endswith('_names'):pass
  elif 'null' not in text:text+=' 当前null表示没有在此处单独设置；按所属功能的默认逻辑处理，不计为未知实测值。'
 issues=[]
 # Only mark physical assumptions/contract fields, not repeated selectors and bookkeeping.
 if 'robot' in p and 'joint_pos' in p:issues=['deployment']
 if 'actuators' in p and k in ('kp_fw','delay_min_lag','delay_max_lag','delay_hold_prob','delay_update_period','armature','frictionloss','viscous_damping','stiff_frictionloss'):issues=['dynamics']
 if 'actuators' in p and k in ('vin','vin_range','vin_drop_gain_range','vin_min'):issues=['power']
 if 'collisions' in p and ('friction' in p or 'condim' in p):issues=['contact']
 if p[:2]==['env','events'] and 'asset_cfg' not in p:
  if p[2]=='foot_friction' and k=='ranges':issues=['contact']
  if p[2] in ('randomize_com','randomize_head_com','base_com','randomize_mass_inertia') and k in ('ranges','alpha_range','0','1','2'):issues=['mass']
  if p[2] in ('randomize_armature','randomize_joint_friction') and k in ('ranges','scale_range'):issues=['dynamics']
  if p[2]=='encoder_bias' and k=='bias_range':issues=['dynamics']
 if p[:3]==['env','observations','actor'] and k in ('max_angle_deg','n_min','n_max','delay_min_lag','delay_max_lag'):
  if p[4] in ('base_ang_vel','projected_gravity'):issues=['dynamics']
  elif p[4] in ('joint_pos','joint_vel'):issues=['dynamics']
 if p[:2]==['env','actions'] and k in ('scale','offset','use_default_offset'):issues=['deployment']
 if p[:2]==['env','curriculum'] and p[2] in ('com_range','head_com_range') and k=='range':issues=['mass']
 # Explicitly not configured values are known inheritance, not unresolved physical numbers.
 if v is None:issues=[]
 return {'title':title,'context':ctx,'explanation':text,'unit':unit,'status':'pending' if issues else 'known',
   'status_label':'本机适配待核对' if issues else '源码已确认', 'issue_ids':issues,
   'evidence':'固定提交的已知源码值；尚未证明覆盖本机实测。' if issues else '固定提交的已知设置；先沿用，无需逐项确认。'}


def missing_help(row,ctx=None):
 path='.'.join(map(str,row.get('path',[])))
 return {'title':str((row.get('path') or ['未命名'])[-1]),'context':ctx or '官方配置',
   'explanation':'该字段的源码值已读取，中文含义与单位尚未收录。保留当前值；说明缺项不会阻止配置读取或启动训练。路径：'+path,
   'unit':'待补充','status':'pending','status_label':'说明待补充','issue_ids':[],
   'documentation_missing':True,'evidence':'仅缺中文说明，不代表源码缺值，也不表示实机参数已确认。'}


def annotate_rows(rows):
 result=[]
 for row in rows:
  try:help=help_for(row)
  except (KeyError,IndexError,TypeError,ValueError):help=missing_help(row)
  result.append({**row,'help':help})
 return result

BAM_HELP={
'kt':('电机力矩常数','单位电流产生的模型力矩，也参与反电动势计算；不要按舵机宣传的堵转扭矩直接代换。','N·m/A'),
'error_gain_ratio':('位置误差增益换算','将固件P值和位置误差换算为模型控制作用的比例。','系数'),
'R':('等效电阻','电气模型中的等效电阻，影响电流与可输出力矩。','Ω'),
'armature':('折算转子惯量','电机和传动的附加转动惯量；与刚体惯量分开。','kg·m²'),
'q_offset':('辨识角度偏移','辨识模型使用的角度偏置，不是本机15关节的编码器零位。','rad'),
'command_delay':('辨识命令延迟','辨识文件记录的延迟；与执行器队列步数是不同字段，不能未经实现核对就直接相加。','s'),
'friction_base':('基础干摩擦','与负载无关的基础摩擦力矩。','N·m'),
'friction_stribeck':('低速附加摩擦','描述低速时额外摩擦力矩及进入运动后的变化。','N·m'),
'load_friction_motor':('电机力矩相关摩擦','摩擦随驱动力矩变化的系数。','系数'),
'load_friction_external':('外部负载相关摩擦','摩擦随外部负载变化的系数。','系数'),
'load_friction_motor_stribeck':('低速电机负载摩擦','低速摩擦中与电机力矩有关的部分。','系数'),
'load_friction_external_stribeck':('低速外部负载摩擦','低速摩擦中与外部负载有关的部分。','系数'),
'load_friction_motor_quad':('电机负载二次摩擦项','乘电机力矩平方的低速摩擦系数；仅在模型规定的负载/驱动方向条件下参与。','1/(N·m)'),
'load_friction_external_quad':('外部负载二次摩擦项','乘外部力矩平方的低速摩擦系数；仅在模型规定的负载/驱动方向条件下参与。','1/(N·m)'),
'dtheta_stribeck':('低速摩擦过渡速度','决定附加低速摩擦在哪个速度尺度衰减。','rad/s'),
'alpha':('低速摩擦曲线形状','控制低速到运动摩擦的过渡曲线形状。','系数'),
'friction_viscous':('黏性摩擦','关节角速度乘此系数得到黏性阻力矩。','N·m·s/rad'),
'max_velocity':('内部目标变化速度上限','Feetech模型限制内部目标角度每秒能改变多快；不等于实机标称或安全转速。','rad/s'),
'model':('辨识模型系列','m6等是BAM模型类别，用来选择计算形式。','名称'),
'actuator':('辨识资产标签','保留上游文件的电机标签；1910文件中写sts3215不代表本机已经完成实测辨识。','名称')}
MODEL_HELP={
'mass_kg':'这一刚体及其固连零件的质量，单位kg；不是单颗舵机自重。',
'mass_g':'同一刚体质量换算成g，便于称重对照。',
'pos':'相对父刚体的位置[x,y,z]，单位m。','quat':'相对父刚体旋转，顺序[w,x,y,z]。',
'ipos':'刚体坐标系中的重心位置[x,y,z]，单位m。',
'inertia':'绕惯性主轴的三个主惯量，单位kg·m²；越大越难改变转速。',
'iquat':'惯性主轴相对刚体系的旋转[w,x,y,z]，须和inertia一起使用。',
'axis':'关节在局部坐标系中绕哪条轴转动。','range':'模型关节允许的角度范围，单位rad；实机机械限位另存。',
'home_rad':'模型默认关节角，单位rad；网络相对角观测和目标偏置依赖它。',
'home_deg':'同一Home换算为度，便于与站姿对照。','parent':'连接在这个刚体前面的父刚体，用于描述机械层级。'}

BC_HELP={
 'wandb_run_path':('官方起身老师来源','官方默认参考；中控启动联合训练时替换为选择的本地起身老师，不下载该W&B模型。','路径'),
 'checkpoint_name':('官方起身老师文件','官方默认参考文件名；本次使用选择的本地起身老师。','文件名'),
 'checkpoint_path':('起身老师实际路径','启动时由本地起身老师选择框填写；用于倾斜超过门槛的采样。','路径'),
 'anchor_wandb_run_path':('官方行走老师来源','官方默认参考；中控用所选本地行走老师作为直立动作锚点。','路径'),
 'anchor_checkpoint_name':('官方行走老师文件','官方默认参考文件名；本次使用选择的本地行走老师。','文件名'),
 'anchor_checkpoint_path':('行走老师实际路径','启动时由本地行走老师选择框填写；新联合任务也从这位老师热启动。','路径'),
 'coef':('起身模仿损失权重 / Recovery BC coefficient','倾斜帧上，学生和起身老师动作均方误差的权重；不是环境奖励。','系数'),
 'anchor_coef':('行走模仿损失权重 / Walk anchor coefficient','直立帧上，约束学生保留行走老师动作的均方误差权重。','系数'),
 'learning_rate':('模仿优化器学习率 / BC learning rate','双教师模仿使用独立Adam；与PPO自适应学习率是两项参数。','学习率'),
 'gate_tilt_deg':('起身老师启用倾角 / Recovery tilt gate','机身倾斜严格大于此角度的采样由起身老师指导。','°'),
 'anchor_tilt_deg':('行走老师启用倾角 / Walk tilt gate','机身倾斜小于等于此角度的采样由行走老师指导；中间区间仅走PPO。','°'),
 'epochs':('每轮模仿遍数 / BC epochs','每次PPO更新后，对所采样姿态进行的模仿训练遍数。','遍'),
 'mini_batches':('模仿小批次数 / BC mini-batches','用于计算小批次大小；整数取整与尾批会使实际批数变化，并非严格更新次数上限。','参考批数'),
 'min_mini_batch':('模仿小批次参考下限 / Minimum mini-batch','按样本量减少小批次数，防止少量倒地帧被过度重复优化。','采样帧'),
 'min_samples':('起身模仿最少样本 / Minimum fallen samples','倒地门控帧不足时跳过起身老师损失；行走锚点仍可继续更新。','采样帧'),
 'gravity_slice':('重力观测位置 / Gravity observation slice','从未归一化观测的这一切片判断机身倾斜；起点含、终点不含。','索引'),
 'twist_slice':('速度命令位置 / Twist command slice','送给起身老师前将这三个速度命令槽清零；行走老师仍读取原命令。','索引'),
}

# Fields newly exposed by the single frozen official source (terrain, sitstand,
# ground-pick and roulade). Units follow mjlab 1.3.0 configs and upstream mdp.py.
for _key, _definition in {
 'bc_cfg':('教师模仿配置','控制双教师模仿损失；null表示本次配置不启用教师BC，评估与导出只加载学生。','配置'),
 'asset_name':('场景对象名称','指定读取或重置哪个场景对象，例如ball是球，robot是机器人。','名称'),
 'noise_xy':('球复位平面扰动','球的复位位置在水平面上的随机扰动范围。','m'),
 'ball_radius':('球半径','用于计算球复位时的离地高度。','m'),
 'max_speed':('计奖速度上限','超过此速度不再继续增加该速度奖励，避免鼓励无限加速。','m/s'),
 'target_speed':('目标速度','速度超调项使用的参考速度，超过后产生相应惩罚。','m/s'),
 'curriculum':('地形难度课程','是否按地形生成器的课程方式安排难度；不是所有训练课程的总开关。','开关'),
 'size':('地形块长宽','每块生成地形在水平面的尺寸[x,y]。','m'),
 'border_width':('地形边界宽度','地形或子地形边缘保留的区域宽度。','m'),
 'border_height':('地形边界高度','生成器外围边界的高度。','m'),
 'num_rows':('地形行数','生成器铺设的地形块行数。','块'),
 'num_cols':('地形列数','生成器铺设的地形块列数。','块'),
 'color_scheme':('地形着色规则','height按高度着色，只改变显示。','枚举'),
 'proportion':('子地形抽样权重','在各类子地形的权重总和中所占比例，决定采样频率。','相对权重'),
 'flat_patch_sampling':('平坦落脚区采样','寻找满足条件的平坦区域供初始化等用途；null表示未配置。','配置'),
 'step_height_range':('台阶高度范围','随地形难度插值的台阶高度上下界。','m'),
 'step_width':('台阶踏面宽度','每一级台阶在水平面上的宽度。','m'),
 'platform_width':('中央平台宽度','地形中央保留的方形平坦平台边长。','m'),
 'holes':('仅保留中心十字区域','为true时只生成中央平台及周围十字区域，其他部分留空。','开关'),
 'grid_width':('网格单元边长','随机方块地形每个方格的水平边长。','m'),
 'grid_height_range':('随机格高度幅度','难度决定扰动幅度，再在该幅度的正负范围内抽取格子高度。','m'),
 'merge_similar_heights':('合并相近高度格','将相邻且高度相近的格子合成更大的几何体，减少碰撞几何数量。','开关'),
 'height_merge_threshold':('合并高度阈值','格子高度合并时使用的高度差阈值。','m'),
 'max_merge_distance':('合并跨度上限','每个方向最多合并多少个相邻网格。','格'),
 'slope_range':('坡度范围','坡面上升高度除以水平距离的范围，随难度插值；不是角度度数。','比值'),
 'inverted':('反向金字塔','为true时中心平台在低处，形成向中心下降的地形。','开关'),
 'horizontal_scale':('高度场水平分辨率','高度场每个采样格在x/y方向的间距。','m/格'),
 'vertical_scale':('高度场垂直分辨率','高度场整数高度单位对应的实际高度。','m/单位'),
 'base_thickness_ratio':('高度场底座厚度比例','底座厚度相对于最大表面高度的比例。','倍'),
 'difficulty_range':('地形难度范围','生成地形时采样的归一化难度区间。','0～1'),
 'add_lights':('生成地形灯光','是否额外给地形添加显示灯光。','开关'),
 'prob':('事件采用概率','符合该事件其他条件时实际采用此扰动的概率；0关闭该扰动。','0～1'),
 'flip_frac':('头部指令反向比例','坐姿头部突变事件中，采用当前头部指令符号反向的比例，其余重新采样。','0～1'),
 'ang_vel_range':('倾倒角速度范围','坐姿倾倒扰动的角速度幅度抽样范围。','rad/s'),
 'lateral_frac':('横向扰动幅度比例','相对主倾倒角速度叠加的横向滚转幅度比例，不是抽样概率。','倍'),
 'sit_z':('坐姿目标高度','坐下状态的躯干目标高度，用于姿态和高度奖励。','m'),
 'stand_z':('站姿目标高度','站立状态的躯干目标高度，用于姿态和高度奖励。','m'),
 'max_vz':('起身速度计奖上限','向上运动奖励的饱和速度，超过后不增加奖励，避免鼓励弹射起身。','m/s'),
 'max_down_vel':('下降速度阈值','下降过快惩罚使用的速度阈值。','m/s'),
 'max_up_vel':('上升速度阈值','上升过快惩罚使用的速度阈值。','m/s'),
 'band_full':('完整静止奖励高度带','高度误差在此带内时，高度门控允许完整静止奖励。','m'),
 'band_zero':('静止奖励截止高度带','高度误差达到此值时静止奖励门控归零，避免过渡中途停住刷奖励。','m'),
 'vel_std':('静止速度宽容度','静止奖励对速度误差的敏感尺度；越大越宽容。','m/s'),
 'head_std':('头部姿态宽容度','综合姿态奖励对头部角度误差使用的尺度。','rad'),
 'tilt_start_deg':('颈部负载惩罚起始倾角','躯干倾斜超过该角度后，逐步开启相应颈部力矩惩罚。','度'),
 'torque_scale':('颈部力矩归一化尺度','颈部力矩除以此值再平方，得到负载惩罚的强弱。','N·m'),
 'class_type':('组件实现类型','该配置构建的指令、传感器或执行器类；保持官方绑定即可。','代码类型'),
 'sit_prob':('坐下指令比例','坐站命令重新采样时，选择坐下目标的概率。','0～1'),
 'ramp_s':('坐站目标过渡时间','目标从站姿到坐姿或反向变化的插值时间。','s'),
 'min_kg':('鸭嘴负载质量下限','模拟鸭嘴携带物品时抽样负载的最小质量。','kg'),
 'max_kg':('鸭嘴负载质量上限','模拟鸭嘴携带物品时抽样负载的最大质量。','kg'),
 'descent_end':('下降阶段结束相位','周期中从站姿过渡到低位的结束位置，按整个周期的比例表示。','0～1'),
 'hold_end':('低位保持结束相位','在低位保持到这个相位后开始返回。','0～1'),
 'rise_end':('返回站姿结束相位','到这个相位完成上升，其余时间保持高位。','0～1'),
 'period':('动作相位周期','完整相位循环所需时间，运行端也必须使用对应周期。','s'),
 'randomize_phase':('随机初始相位','复位时随机各环境相位以分散样本；false从相位0开始。','开关'),
 'midroll_prob':('翻滚中途起始权重','复位时从翻滚中间姿态开始的相对权重，与站姿权重共同归一化。','相对权重'),
 'standing_tilt_max':('站姿初始最大倾角','翻滚复位中正常站姿的随机倾斜范围上限。','rad'),
 'forward_vel_range':('初始前向速度范围','翻滚复位时沿前方施加的初始速度抽样区间。','m/s'),
 'midroll_pitch_min':('中途姿态俯仰下限','翻滚中途初始姿态的俯仰角采样下限。','rad'),
 'midroll_pitch_max':('中途姿态俯仰上限','翻滚中途初始姿态的俯仰角采样上限。','rad'),
 'midroll_z_min':('中途姿态高度下限','翻滚中途复位时的初始躯干高度下限。','m'),
 'midroll_z_max':('中途姿态高度上限','翻滚中途复位时的初始躯干高度上限。','m'),
 'midroll_omega_range':('中途姿态角速度范围','翻滚中途初始状态沿翻滚方向的角速度抽样区间。','rad/s'),
 'tuck_factor_range':('抱身姿态混合范围','复位时在默认姿态与指定抱身关节目标之间插值的系数范围。','0～1'),
 'joint_noise_std':('初始关节角噪声','在复位参考关节角上叠加的随机角度噪声标准差。','rad'),
 'target_angle':('目标累计翻转角','完成一次翻滚要求累计的前向翻转角，2π为一整圈。','rad'),
 'max_paid_rate':('翻滚进度计奖速度上限','对每步可获得奖励的进度增量限速，避免过度追求快速旋转。','rad/s'),
 'omega_max':('翻滚超速阈值','前向翻滚角速度超过此值后施加超速惩罚。','rad/s'),
 'angle_lo':('接触计奖起始角','累计翻滚角进入该窗口后才开启相应支点奖励。','rad'),
 'angle_hi':('接触计奖结束角','累计翻滚角超过窗口上限后结束相应支点奖励。','rad'),
 'rate_norm':('支点奖励角速度尺度','翻滚角速度除以此值并裁剪到0～1，用于接触支点奖励。','rad/s'),
 'gate_lo':('落地奖励开启角','累计翻滚角达到该值后开始渐进开启相应恢复或落地奖励。','rad'),
 'gate_hi':('落地奖励完全开启角','累计翻滚角达到该值后相应角度门控完全开启。','rad'),
 'use_data_augmentation':('使用镜像样本增强','把观测和动作按指定对称函数变换，加入训练样本。','开关'),
 'use_mirror_loss':('使用镜像一致性损失','约束对称变换前后策略输出的对应关系。','开关'),
 'mirror_loss_coeff':('镜像损失系数','镜像一致性损失在优化中的权重。','系数'),
 'data_augmentation_func':('对称变换函数','负责交换左右关节及相关符号、变换观测和动作的官方函数。','代码入口'),
}.items():
 DEFS.setdefault(_key, _definition)
