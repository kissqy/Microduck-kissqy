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
  return formatError(raw,fallback);
}

/** Translate only at display boundaries; never alter replies, logs or recordings. */
export function formatError(value,fallback='操作未完成，原始错误如下。') {
  let raw=String(value?.message??value??'').trim();
  if(!raw)return '';
  // DOMException names can be the only indication of a denied device permission.
  const name=value?.name;
  if(/^(?:NotAllowed|NotFound|NotReadable|Overconstrained|Security|Timeout|Abort)Error$/.test(name||'')&&!raw.includes(name))raw=name+': '+raw;
  if(raw.includes('\n原始错误：'))return raw;
  const rules=[
    [/host key verification failed|remote host identification has changed/i,'SSH 主机身份校验未通过，请核对 Zero 的主机密钥；重刷系统后原有记录可能已不匹配。'],
    [/permission denied[^\n]*\([^)]*(?:publickey|password)|authentication failed|incorrect password|sorry, try again/i,'SSH 或 sudo 登录验证失败，请检查登录账号、密码或密钥。'],
    [/read-only file system|errno\s*30\b/i,'文件系统处于只读状态，无法写入文件。'],
    [/no space left on device|errno\s*28\b/i,'存储空间已满，无法继续写入。'],
    [/python3[^\n]*(?:not found|command not found)/i,'Zero 上未找到 Python 3，当前功能无法启动。'],
    [/no such file or directory|errno\s*2\]|filenotfounderror/i,'找不到所需文件或服务接口，请检查文件路径及对应服务。'],
    [/NotAllowedError|permissiondismissed|permissiondenied|permission denied by system|user denied|permission.*(?:microphone|camera)|(?:microphone|camera).*permission/i,'浏览器未获得摄像头、麦克风或媒体播放权限，请检查浏览器权限设置。'],
    [/NotReadableError|could not start (?:video|audio) source|device in use/i,'无法读取摄像头或麦克风，设备可能被占用或暂不可用。'],
    [/NotFoundError|requested device not found|no (?:audio|video) input devices/i,'未找到可用的摄像头或麦克风设备。'],
    [/OverconstrainedError|constraint.*not satisfied/i,'当前摄像头或麦克风不支持请求的采集参数。'],
    [/SecurityError|insecure context|secure context/i,'浏览器安全限制阻止了此操作，请通过中控启动器打开页面并检查浏览器权限。'],
    [/permission denied|errno\s*13\b|access is denied|access denied|operation not permitted|errno\s*1\]/i,'访问权限不足，当前操作未获得所需权限。'],
    [/invalid[_ -]?api[_ -]?key|missing[^\n]*(?:api[_ -]?key|access[_ -]?token)|(?:api[_ -]?key|access[_ -]?token)[^\n]*(?:invalid|required|missing|not set)|unauthorized|invalid (?:token|credentials)/i,'AI 服务身份验证未通过，请检查对应服务的 KEY、令牌或账号配置。'],
    [/rate[_ -]?limit|too many requests|quota exceeded|insufficient[_ ]quota/i,'服务请求次数或额度已达到限制，请检查服务额度并稍后再试。'],
    [/HTTP\s*401\b|status(?:[_ ]code)?[\s:=]+401\b/i,'服务身份验证未通过，请检查登录凭据或 AI 服务 KEY。'],
    [/HTTP\s*403\b|status(?:[_ ]code)?[\s:=]+403\b|forbidden/i,'服务拒绝了此请求，请检查账号权限及配置。'],
    [/HTTP\s*404\b|status(?:[_ ]code)?[\s:=]+404\b/i,'请求的服务地址或接口不存在，请检查服务地址。'],
    [/HTTP\s*409\b|status(?:[_ ]code)?[\s:=]+409\b/i,'当前状态与请求冲突，请查看实时状态后再操作。'],
    [/HTTP\s*413\b|payload too large|request entity too large/i,'提交的数据或文件过大，请检查文件大小。'],
    [/HTTP\s*429\b|status(?:[_ ]code)?[\s:=]+429\b/i,'服务请求过于频繁，请稍后再试。'],
    [/HTTP\s*(?:400|405|422)\b|status(?:[_ ]code)?[\s:=]+(?:400|405|422)\b/i,'服务未接受请求参数或操作方式，请检查当前设置。'],
    [/HTTP\s*5\d\d\b|status(?:[_ ]code)?[\s:=]+5\d\d\b|bad gateway|service unavailable|internal server error/i,'服务端暂时无法完成请求，请检查服务状态或稍后再试。'],
    [/could not resolve hostname|name or service not known|temporary failure in name resolution|getaddrinfo|ENOTFOUND/i,'无法解析服务主机名，请检查地址及网络连接。'],
    [/network is unreachable|no route to host|ENETUNREACH|EHOSTUNREACH/i,'无法访问目标设备或服务，请检查网络连接与地址。'],
    [/connection refused|errno\s*111\b|ECONNREFUSED/i,'目标服务拒绝连接，请检查地址、端口及对应服务是否已启动。'],
    [/connection reset|broken pipe|connection closed|connection (?:was )?lost|ECONNRESET|EPIPE/i,'连接已中断；本次操作是否完成请查看实际状态。'],
    [/timed? out|timeout|TimeoutError|ETIMEDOUT|HTTP\s*408\b/i,'等待响应超时，尚未确认本次操作完成。'],
    [/AbortError|operation was aborted|signal is aborted/i,'请求已取消或等待已终止，尚未确认本次操作完成。'],
    [/failed to fetch|fetch failed|networkerror|network request failed|load failed/i,'浏览器无法访问中控或目标服务，请检查连接与启动终端。'],
    [/RTCError|setRemoteDescription|setLocalDescription|ICE (?:failed|connection)|SDP|WebRTC.*(?:failed|error)/i,'摄像头 WebRTC 连接协商失败，请检查摄像头服务及网络连接。'],
    [/complete but transaction deadline exceeded/i,'反馈已完整返回，但超过了本轮读取截止时间。'],
    [/unexpected token|unexpected end of JSON|JSONDecodeError|not valid JSON|JSON\.parse/i,'收到的数据格式不完整或不是有效 JSON，请检查对应服务和原始回执。'],
    [/Traceback \(most recent call last\)|\b(?:Runtime|Type|Value|Attribute|Key|Index|OS|Import|ModuleNotFound)Error\b/i,'程序执行出现异常，具体原因见原始错误。']
  ];
  const match=rules.find(([pattern])=>pattern.test(raw));
  if(match)return match[1]+'\n原始错误：'+raw;
  // Chinese operator messages and identifiers/units are already readable.
  if(/[\u3400-\u9fff]/.test(raw)&&!/[A-Za-z]{3,}(?:[ \t]+[A-Za-z]{3,}){2}/.test(raw))return raw;
  return (fallback||'操作未完成，原始错误如下。')+'\n原始错误：'+raw;
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
