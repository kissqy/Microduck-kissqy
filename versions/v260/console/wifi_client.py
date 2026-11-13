"""On-demand Zero Wi-Fi management through the existing privileged SSH channel."""
from collections import OrderedDict
import copy
import hashlib
import json
from pathlib import Path
import re
import threading

from controls import ControlError


def validate_request(payload):
    if not isinstance(payload, dict):
        raise ControlError('Wi-Fi 请求必须是对象', 400)
    action = payload.get('action')
    fields = {
        'status': {'action'}, 'scan': {'action'},
        'connect': {'action', 'ssid', 'uuid', 'password', 'request_id'},
        'forget': {'action', 'uuid', 'request_id'}, 'job': {'action', 'job_id'},
    }
    if not isinstance(action, str) or action not in fields or set(payload) != fields[action]:
        raise ControlError('Wi-Fi 操作或参数无效', 400)
    if action == 'connect':
        ssid, password = payload['ssid'], payload['password']
        try:
            ssid_bytes = len(ssid.encode('utf-8')) if isinstance(ssid, str) else 0
        except UnicodeEncodeError:
            ssid_bytes = 0
        if (not isinstance(ssid, str) or not 1 <= ssid_bytes <= 32
                or any(c in ssid for c in '\r\n\0')):
            raise ControlError('Wi-Fi 名称须为 1–32 字节，且不能含换行或空字符', 400)
        if (not isinstance(password, str) or len(password) > 256
                or any(c in password for c in '\r\n\0')):
            raise ControlError('Wi-Fi 密码格式无效', 400)
    if action in ('connect', 'forget'):
        if not isinstance(payload['request_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', payload['request_id']):
            raise ControlError('Wi-Fi 操作请求标识无效，请刷新页面', 400)
        uuid = payload['uuid']
        if not isinstance(uuid, str) or (not uuid and action == 'forget') or (uuid and not re.fullmatch(
                r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', uuid)):
            raise ControlError('已保存 Wi-Fi 的标识无效，请重新扫描', 400)
    if action == 'job' and (not isinstance(payload['job_id'], str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', payload['job_id'])):
        raise ControlError('Wi-Fi 连接任务标识无效', 400)
    return dict(payload)


class WiFiClient:
    def __init__(self, transport):
        self.transport = transport
        self.lock = threading.Lock()
        self.receipts = OrderedDict()

    def request(self, payload):
        request = validate_request(payload)
        if not self.lock.acquire(blocking=False):
            raise ControlError('Wi-Fi 操作正在进行，请稍候', 409)
        try:
            return self._request(request)
        finally:
            self.lock.release()

    def _request(self, request):
        request_id = request.pop('request_id', None)
        fingerprint = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if request_id in self.receipts:
            old_fingerprint, receipt = self.receipts[request_id]
            if old_fingerprint != fingerprint:
                raise ControlError('同一个 Wi-Fi 请求标识不能用于不同操作，请重新选择网络', 409)
            if isinstance(receipt, ControlError):
                raise ControlError(str(receipt), receipt.status)
            return copy.deepcopy(receipt)
        secret = request.get('password', '')
        log = getattr(self.transport, 'log', None)
        if log:
            log.hide(secret)
        try:
            # The helper is sent as code; credentials are only in stdin. No
            # firmware installation or persistent network service is required.
            source = Path(__file__).with_name('wifi_manager.py').read_text(encoding='utf-8')
            receipt = self.transport._manage(
                ['python3', '-u', '-c', source], record_output=False,
                input_data=json.dumps(request, ensure_ascii=False) + '\n',
                redact_values=(secret,))
            if not isinstance(receipt, dict) or type(receipt.get('accepted')) is not bool:
                raise ControlError('Wi-Fi 操作没有返回有效回执，请检查 SSH 连接', 503)
            if not receipt['accepted']:
                message = receipt.get('error') or receipt.get('message') or 'Wi-Fi 操作未完成'
                raise ControlError(str(message), 409)
        except Exception as exc:
            message = str(exc).replace(secret, '[已隐藏]') if secret else str(exc)
            if not isinstance(exc, ControlError):
                message = 'Wi-Fi 操作连接中断，结果尚未确认；请检查 SSH 连接后刷新列表'
            error = ControlError(message, getattr(exc, 'status', 503))
            if request_id:
                self._remember(request_id, fingerprint, error)
            raise error from None
        if request_id:
            self._remember(request_id, fingerprint, copy.deepcopy(receipt))
        return receipt

    def _remember(self, request_id, fingerprint, receipt):
        self.receipts[request_id] = (fingerprint, receipt)
        while len(self.receipts) > 64:
            self.receipts.popitem(last=False)
