"""Read-only view of the console's existing tofd telemetry; never opens a device."""
import math
import statistics


def distance_snapshot(snapshot, capture_t_ns=None):
    note = 'TOF 是头部前方8×8测距，未与照片逐像素配准；中心距离不一定属于被问的物体。'
    unavailable = lambda reason: {'available':False, 'source':'tofd_cached_frame', 'reason':reason, 'note':note}
    frame = snapshot.get('tof') or {}
    channel = (snapshot.get('channels') or {}).get('tof') or {}
    age = channel.get('age_ms')
    if (channel.get('status') != 'live' or type(age) not in (int,float)
            or not math.isfinite(age) or not 0 <= age <= 1000):
        return unavailable('没有1秒内的新鲜 TOF 测距，不能给出物体距离')
    distances, statuses = frame.get('distance_mm'), frame.get('status')
    if (frame.get('rows') != 8 or frame.get('cols') != 8
            or not isinstance(distances,list) or len(distances) != 64
            or not isinstance(statuses,list) or len(statuses) != 64):
        return unavailable('TOF 分区数据不完整')
    t_ns = frame.get('t_ns')
    delta = None
    if capture_t_ns is not None:
        if type(t_ns) is not int or t_ns <= 0 or type(capture_t_ns) is not int or capture_t_ns <= 0:
            return unavailable('TOF 没有同机单调时钟时间，无法核对本次取图时间')
        delta = round((t_ns-capture_t_ns)/1_000_000,1)
        if abs(delta) > 1000:
            return unavailable('TOF 与本次取图相差超过1秒，不能作为本次物体距离')
    # Match tof::Frame::zone: only ST status 5/9 with a positive distance is a range.
    grid = [round(mm/1000,3) if type(mm) is int and mm > 0 and type(status) is int and status in (5,9)
            else None for mm,status in zip(distances,statuses)]
    valid = [value for value in grid if value is not None]
    if not valid:return unavailable('TOF 没有有效距离；无目标或本次测量不可用')
    center = [grid[i] for i in (27,28,35,36) if grid[i] is not None]
    return {'available':True, 'source':'tofd_cached_frame', 'unit':'m',
            'seq':frame.get('seq'), 'sample_t_ns':t_ns, 'age_ms':round(age,1),
            'capture_delta_ms':delta, 'alignment':'near_capture_not_pixel_registered',
            'center_m':round(statistics.median(center),3) if center else None,
            'center_valid_zones':len(center), 'valid_zones':len(valid),
            'nearest_m':min(valid), 'farthest_m':max(valid),
            'grid_m':[grid[row*8:(row+1)*8] for row in range(8)],
            'orientation':'TOF原生行列：第0行为上，第0列为传感器左侧；不等于照片像素坐标',
            'note':note}
