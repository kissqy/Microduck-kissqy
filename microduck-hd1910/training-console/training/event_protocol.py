"""Framed dashboard events, independent of human-readable training output."""
import json
import sys
import threading

PREFIX = 'MICRODUCK_ADAPTER '
KINDS = frozenset(('log','task_config','effective_config','viewer_ready','sim_state',
                  'validation','training_view_ready','training_view_state',
                  'training_view_error','training_curriculum_state','sample_clock'))
_LOCK = threading.Lock()
def _nonfinite(value):
    raise ValueError('JSON 含有非有限数值：'+value)


_DECODER = json.JSONDecoder(parse_constant=_nonfinite)


def emit(kind, **data):
    # print(..., flush=True) writes the message and newline separately.
    frame = PREFIX+json.dumps({'kind':kind, **data},ensure_ascii=False,allow_nan=False)+'\n'
    with _LOCK:
        sys.stdout.write(frame)
        sys.stdout.flush()


def split_output(line):
    """Yield ('event', dict) or ('log', str), preserving mixed-output order.

    raw_decode consumes exactly one JSON object. Trailing logs and subsequent
    messages remain visible instead of raising Extra data into the supervisor.
    A malformed telemetry frame is diagnosed, not mistaken for a trainer exit.
    """
    offset = 0
    adjacent = False
    while offset < len(line):
        tail = line[offset:]
        marker = line.find(PREFIX, offset)
        if adjacent and tail.lstrip().startswith('{'):
            begin = offset + len(tail)-len(tail.lstrip())
        elif marker >= 0:
            if line[offset:marker].strip(): yield 'log', line[offset:marker].strip()
            begin = marker+len(PREFIX)
            begin += len(line[begin:])-len(line[begin:].lstrip())
        else:
            if tail.strip(): yield 'log', tail.strip()
            return
        try:
            event, end = _DECODER.raw_decode(line, begin)
        except (ValueError, RecursionError) as error:
            following = line.find(PREFIX, begin)
            end = following if following >= 0 else len(line)
            yield 'log', '[中控消息异常] 已保留原始输出，继续接收训练结果：'+str(error)
            yield 'log', line[begin:end]
            offset, adjacent = end, False
            continue
        if isinstance(event,dict) and isinstance(event.get('kind'),str) and event['kind'] in KINDS:
            yield 'event', event
        else:
            yield 'log', '[中控消息异常] 未识别的消息：'+line[begin:end]
        offset, adjacent = end, True
