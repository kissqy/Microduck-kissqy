// Presentation only. Keep upstream messages unchanged in JSON and recordings.
export function messageZh(value, fallback='服务返回了异常，具体报文可在“查看 JSON”中查看。') {
  const raw=String(value??'').trim();
  if(!raw)return '';
  let m;
  if((m=raw.match(/^no robot on the motor bus after (\d+) attempts; is servo power on and the bus wired\?$/i)))
    return `舵机总线初始化尚未成功，已重试 ${m[1]} 次。请检查舵机供电、接线，以及官方配置的 15 颗舵机是否齐全、编号是否正确。`;
  if(raw==='control loop has not completed a cycle yet')return '控制程序正在启动，尚未完成首个控制周期。';
  if(raw==='forced unhealthy by --unhealthy')return '控制程序启用了强制异常测试参数。';
  if((m=raw.match(/^(\d+) consecutive bus read failures$/)))return `舵机总线已连续读取失败 ${m[1]} 次。`;
  if((m=raw.match(/^control loop stalled for (\d+) ms$/)))return `控制循环已停滞 ${m[1]} 毫秒。`;
  if((m=raw.match(/^control loop at ([\d.]+) Hz, below the ([\d.]+) Hz floor$/)))return `控制频率为 ${m[1]} Hz，低于 ${m[2]} Hz 的最低要求。`;
  if(raw.startsWith('policy unavailable:'))return '运动策略不可用。'+messageZh(raw.slice(19),'策略加载失败，具体报文可在“查看 JSON”中查看。');
  if(raw==='bringing the sensor up')return '测距传感器正在初始化，等待首帧数据。';
  if(raw==='the sensor stopped answering; retrying')return '测距传感器停止响应，官方服务正在重试。';
  if(raw==='the sensor stopped answering')return '测距传感器停止响应。';
  if(raw==='no bus to look on')return '未找到可供测距传感器使用的 I²C 总线。';
  if(raw==='a sensor is already open in this process')return '当前进程已打开一个测距传感器。';
  if((m=raw.match(/^(\/\S+) does not exist$/)))return `测距总线设备 ${m[1]} 不存在，请检查 I²C 接口配置。`;
  if((m=raw.match(/^(\/\S+) is not a usable device path$/)))return `测距总线设备路径 ${m[1]} 无效。`;
  if((m=raw.match(/^nothing answered at (0x[\da-f]+) on (\S+)$/i)))return `在 ${m[2]} 的地址 ${m[1]} 未收到传感器响应（这是官方服务最后一次探测的结果）。`;
  if((m=raw.match(/^cannot open (\/\S+)$/)))return `无法打开测距总线 ${m[1]}，请检查设备与访问权限。`;
  if((m=raw.match(/^(\S+) firmware upload failed \(ULD status (\d+)\)$/)))return `${m[1]} 传感器固件加载失败，驱动状态码 ${m[2]}。`;
  if((m=raw.match(/^start ranging at (\d+) Hz failed \(ULD status (\d+)\)$/)))return `启动 ${m[1]} Hz 测距失败，驱动状态码 ${m[2]}。`;
  if((m=raw.match(/^reading the frame failed \(ULD status (\d+)\)$/)))return `读取测距数据失败，驱动状态码 ${m[1]}。`;
  if((m=raw.match(/^the (\S+) stopped answering between the probe and the handshake$/)))return `${m[1]} 探测后在握手过程中停止响应。`;
  if((m=raw.match(/^something at (0x[\da-f]+) answered with device (0x[\da-f]+) revision (0x[\da-f]+), which is neither a VL53L5CX nor a VL53L8CX$/i)))return `地址 ${m[1]} 的设备型号不受支持：设备码 ${m[2]}、版本码 ${m[3]}，需要 VL53L5CX 或 VL53L8CX。`;
  if(/host key verification failed|remote host identification has changed/i.test(raw))return 'SSH 主机身份验证失败，请先在终端核验 Zero 的主机密钥。';
  if(/permission denied.*publickey/i.test(raw))return 'SSH 密钥认证失败，请确认当前 Windows 账号可以免密登录 Zero。';
  if(/permission denied|errno 13|access is denied/i.test(raw))return '访问权限不足，请检查登录账号读取该服务接口的权限。';
  if(/no such file or directory|errno 2\]/i.test(raw))return '找不到对应文件或服务接口，请检查相关服务是否已启动。';
  if(/connection refused|errno 111/i.test(raw))return '服务拒绝连接，请检查对应服务是否正在运行。';
  if(/connection reset|broken pipe|connection closed|connection timed out|timed out/i.test(raw))return '数据连接已中断或超时，正在重试。';
  if(/could not resolve hostname|name or service not known/i.test(raw))return '无法解析 Zero 的主机名，请检查连接地址。';
  if(/network is unreachable|no route to host/i.test(raw))return '无法访问 Zero，请检查局域网连接。';
  if(/python3.*(?:not found|command not found)/i.test(raw))return 'Zero 上未找到 Python 3，采集器无法启动。';
  if(raw.startsWith('SSH 中断'))return 'SSH 数据采集已中断，正在重试；具体报文可在“查看 JSON”中查看。';
  // Existing Chinese messages may contain identifiers/units, but not English sentences.
  if(/[\u3400-\u9fff]/.test(raw)&&!/[A-Za-z]{3,}(?:[ \t]+[A-Za-z]{3,}){2}/.test(raw))return raw;
  return fallback;
}

export function tofView(snapshot) {
  const c=snapshot.channels?.tof||{},f=snapshot.tof||{},sub=f.subscription;
  const validFrame=Number.isInteger(f.rows)&&Number.isInteger(f.cols)&&f.rows>0&&f.cols>0&&f.rows*f.cols<=256&&Array.isArray(f.distance_mm)&&f.distance_mm.length===f.rows*f.cols&&Array.isArray(f.status)&&f.status.length===f.rows*f.cols;
  if(c.status==='error')return {validFrame,status:'error',label:'连接异常',detail:messageZh(c.error)||'测距数据连接异常，正在重试。'};
  if(validFrame&&c.status==='live')return {validFrame,status:'live',label:`${f.rows}×${f.cols} · 实时`,detail:'正在接收有效测距帧。'};
  const reason=messageZh(sub?.unavailable,'测距传感器未就绪，具体原因可在“查看 JSON”中查看。');
  if(validFrame)return {validFrame,status:'stale',label:'数据过期',detail:reason||'测距数据已停止更新，灰显矩阵保留的是上一次测量。'};
  const starting=sub?.unavailable==='bringing the sensor up';
  return {validFrame,status:reason&&!starting?'unavailable':'waiting',label:reason?(starting?'初始化中':'传感器未就绪'):'等待测距帧',detail:reason||(sub?'测距服务已连接，尚未收到测距帧。':'等待测距服务连接与首帧数据。')};
}
