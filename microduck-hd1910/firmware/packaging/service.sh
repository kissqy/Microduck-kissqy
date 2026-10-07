#!/usr/bin/env bash
# Manages the existing official service. All motor commands go through robotd's socket.
set -Eeuo pipefail
# Root runs installation in a user-owned staging tree; keep it free of root
# bytecode directories so later cleanup does not leave permission errors.
export PYTHONDONTWRITEBYTECODE=1
bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
install_dir=/opt/robot/feetech-ft5-r5
config_dir=/etc/robot/feetech-ft5
params_path=$config_dir/robotd.toml
calibration_path=$config_dir/hd1910-calibration.toml
dropin=/etc/systemd/system/robotd.service.d/zzzz-r17-0151.conf
runtime_dropins=/run/systemd/system/robotd.service.d
state_dir=/var/lib/robot/feetech-ft5/r5
socket_path=/run/robotd.sock
temporary_dir=
input_paused=0
install_phase=idle
service_user=root
service_group=robot
bus_port=/dev/ttyS2

fail() { echo "错误：$*" >&2; return 1; }
require_root() { [[ $EUID -eq 0 ]] || fail '请用 sudo bash service.sh 执行。'; }
require_installed() { [[ -x $install_dir/robotd ]] || fail '请先执行 install。'; }
client() { "$install_dir/robotd" --socket "$socket_path" --params "$params_path" "$@"; }
restart_service() {
    systemctl reset-failed robotd.service
    local result=0
    systemctl restart robotd.service || result=$?
    if [[ $result != 0 ]]; then
        echo 'robotd 启动失败；未重建配置或重复启动。实际错误：' >&2
        journalctl -u robotd.service -n 30 --no-pager -o cat >&2 || true
        return "$result"
    fi
}

on_error() {
    local result=$?
    trap - ERR
    if [[ -n $temporary_dir ]]; then rm -rf -- "$temporary_dir"; fi
    if [[ $input_paused == 1 ]]; then
        echo "安装未完成；阶段：$install_phase；以上为实际错误，可直接重新升级。" >&2
    fi
    exit "$result"
}
trap on_error ERR

identity() {
    service_user=$(systemctl show robotd.service -p User --value)
    service_group=$(systemctl show robotd.service -p Group --value)
    service_user=${service_user:-root}
    service_group=${service_group:-$(id -gn "$service_user")}
    id "$service_user" >/dev/null
    getent group "$service_group" >/dev/null
}

write_dropin() {
    local mode=$1
    python3 "$install_dir/runtime.py" configure-startup "$mode"
    systemctl daemon-reload
}


verify_motion_models() {
    local running
    running=$(systemctl show robotd.service -p ExecStart --value)
    if [[ $running != *--commissioning* ]]; then python3 "$install_dir/runtime.py" verify-models; fi
}


relax_service() {
    python3 "$bundle_dir/runtime.py" relax-confirmed
}

request_relax_service() {
    # Recovery must also work after initialization failed. Request a stop when
    # IPC is reachable, then stop the sole bus owner before reopening the HAT.
    python3 "$bundle_dir/runtime.py" relax-request
}

show_service() {
    systemctl show robotd.service -p ActiveState -p SubState -p MainPID -p ExecStart --no-pager
}

install_bundle() {
    # Requested model replacement: no deployment snapshot, rollback or readiness gate.
    local install_mode=commissioning
    local model_args=()
    [[ ${1:-} != reset-models ]] || model_args=(--replace-models)
    install_phase=preparing
    identity
    temporary_dir=$(mktemp -d)
    python3 "$bundle_dir/rebuild-config.py" --prepare "$temporary_dir"
    local base_args=(--source "$temporary_dir/robotd.toml")
    local previous_args=()
    if [[ -f $install_dir/robotd-profile.toml ]]; then
        previous_args=(--previous-overrides "$install_dir/robotd-profile.toml")
    fi
    if [[ -n ${2:-} && $2 == --base-params ]]; then
        base_args=(--source "$3")
    fi
    python3 "$bundle_dir/configure.py" "${base_args[@]}" "${previous_args[@]}" "${model_args[@]}" --overrides "$bundle_dir/robotd-profile.toml" --output "$temporary_dir/robotd.toml"
    install_mode=commissioning
    if [[ -f $temporary_dir/hd1910-calibration.toml ]]; then
        if python3 -c 'import sys,tomllib; sys.exit(tomllib.load(open(sys.argv[1],"rb")).get("motion_enabled") is not True)' "$temporary_dir/hd1910-calibration.toml"; then
            install_mode=motion
        fi
    fi
    if [[ ${1:-} == reset-models ]]; then
        echo '已明确要求重置模型：恢复随包模型与默认绑定（LB 手动起身使用 11000 轮老师）；保留本机标定与官方动作缩放。'
    else
        echo '本次升级清理旧 7000／平地 10000 轮起身及 18000 轮联合模型；恢复损坏的随包合同，LB 使用 11000 轮老师，基础系数 1.0；保留当前行走、本机标定和参数。'
    fi
    # padd is a separate official daemon. Stop both input producers before
    # replacing their executable/code; robotd alone does not stop padd.
    input_paused=1
    install_phase=stopping
    # Stopping an absent/already stopped service is optional during replacement.
    # Atomic file installation also avoids truncating running executable inodes.
    systemctl stop microduck-webpad.socket microduck-webpad.service padd.service gamesir-xboxd.service 2>/dev/null || echo '旧输入服务停止返回非零，继续直接升级。'
    request_relax_service || true
    systemctl stop robotd.service || true
    if [[ $bundle_dir != "$install_dir" ]]; then
        install_phase=replacing
        install -d -m 755 "$install_dir"
        python3 "$bundle_dir/install-files.py" "$bundle_dir" "$install_dir" "${model_args[@]}"
    fi
    chmod 755 "$install_dir/robotd" "$install_dir/service.sh" "$install_dir/configure.py"
    install_phase=configuring
    install -d -m 755 -o "$service_user" -g "$service_group" "$config_dir"
    python3 - "$temporary_dir/robotd.toml" "$params_path" "$install_dir" <<'PYPARAMS'
from pathlib import Path
import sys
sys.path.insert(0,sys.argv[3])
from configure import atomic_write
path=Path(sys.argv[2]);data=Path(sys.argv[1]).read_bytes()
atomic_write(path,data)
atomic_write(path.with_name(path.stem+'.saved'+path.suffix),data)
PYPARAMS
    chown "$service_user:$service_group" "$params_path"
    if [[ -f $temporary_dir/hd1910-calibration.toml ]]; then
        python3 "$install_dir/calibration-config.py" copy "$temporary_dir/hd1910-calibration.toml" --output "$calibration_path"
        chown "$service_user:$service_group" "$calibration_path"
    fi
    install_phase=audio-setup
    python3 "$install_dir/voice-setup.py" "$params_path"
    chown "$service_user:$service_group" "$params_path"
    python3 "$install_dir/runtime.py" configure-startup "$install_mode"
    install_phase=input-setup
    python3 "$install_dir/gamepad.py" prepare-all "$install_dir"
    systemctl daemon-reload
    install_phase=robotd-start
    echo '正在启动 robotd；启动失败直接返回错误。'
    restart_service
    install_phase=input-start
    echo '正在启动真实手柄、padd 与网页输入监听；网页工作进程按需启动。'
    systemctl start gamesir-xboxd.service microduck-webpad.socket padd.service
    input_paused=0
    rm -rf -- "$temporary_dir"; temporary_dir=
    install_phase=finished
    echo "R17 / 0.15.1 文件与配置已安装，服务已启动：$install_mode。"
    echo '安装不自动开始运动；后续模型继续从中控导入。'
    echo "{\"upgrade_installed\":true,\"mode\":\"$install_mode\",\"input_setup_complete\":true}"
}

if [[ ${1:-} == models || ${1:-} == connection ]]; then
    python3 "$bundle_dir/runtime.py" "$1"
    exit 0
fi
require_root
if [[ ${1:-} == power || ${1:-} == power-relaxed ]]; then
    [[ $# -eq 2 ]] || fail '用法：power {reboot|shutdown}'
    python3 "$bundle_dir/runtime.py" power "$2"
    exit 0
fi
exec 9>/run/microduck-service-management.lock
flock -n 9 || fail '已有服务管理操作正在执行。'
case ${1:-install} in
install|start) install_bundle "$@" ;;
upgrade)
    [[ $# -eq 1 ]] || fail '用法：upgrade'
    install_bundle "$@"
    ;;
status)
    require_installed
    show_service
    python3 "$install_dir/runtime.py" connection
    client bus-status
    python3 "$install_dir/uart-service.py" status
    ;;
reset-models)
    [[ $# -eq 1 ]] || fail '用法：reset-models（明确恢复随包模型并删除其他模型）'
    install_bundle "$@"
    ;;
report)
    require_installed
    report_path=$(mktemp /tmp/robotd-ft5-r5-XXXXXX.json)
    if client bus-status > "$report_path"; then chmod 644 "$report_path"; cat "$report_path"; echo "报告：$report_path" >&2; else rm -f -- "$report_path"; exit 1; fi
    ;;
bus)
    require_installed
    shift
    client bus "$@"
    ;;
enable)
    require_installed
    effective_mode=$(systemctl show robotd.service -p ExecStart --value)
    [[ $effective_mode == *"$install_dir/robotd"* ]] || fail '当前服务路径不匹配，请先 install。'
    if [[ $effective_mode != *--commissioning* ]]; then
        if python3 "$install_dir/runtime.py" verify-running motion "$bus_port"; then
            echo '当前已经是 HAT 运动循环。'
            show_service
            exit 0
        fi
    fi
    # The helper validates the saved calibration, then opts into the motion backend.
    python3 "$install_dir/calibration-config.py" check "$calibration_path"
    identity
    request_relax_service
    systemctl stop robotd.service
    python3 "$install_dir/calibration-config.py" enable "$calibration_path"
    chown "$service_user:$service_group" "$calibration_path"
    write_dropin motion
    restart_service
    python3 "$install_dir/runtime.py" verify-ready motion
    python3 "$install_dir/runtime.py" verify-calibration
    verify_motion_models
    show_service
    echo '已切入运动模式；有效反馈和 Home 条件满足后可站起测试。'
    ;;
disable)
    require_installed
    switch_mode=commissioning
    current_exec=$(systemctl show robotd.service -p ExecStart --value)
    [[ $current_exec == *"$install_dir/robotd"* ]] || fail '先升级正式服务再切换诊断模式。'
    request_relax_service
    systemctl stop robotd.service
    write_dropin "$switch_mode"
    restart_service
    python3 "$install_dir/runtime.py" verify-ready commissioning
    python3 "$install_dir/runtime.py" verify-calibration
    show_service
    echo "已请求停扭矩并切换同一服务到 $switch_mode；实际总线状态见上方。"
    ;;
relax)
    require_installed
    relax_service
    ;;
init|enable-policy|disable-policy)
    require_installed
    shift_command=$1
    shift
    client "$shift_command" "$@"
    ;;
reconnect)
    require_installed
    [[ $# -eq 1 ]] || fail '用法：reconnect'
    request_relax_service
    restart_service
    python3 "$install_dir/gamepad.py" ensure-webpad
    systemctl start padd.service gamesir-xboxd.service
    echo 'robotd 已按现有配置重新启动；输入连接复用，不重写配置。'
    ;;
model-import)
    require_installed
    [[ $# -eq 4 ]] || fail '用法：model-import 完整ZIP路径 文件名 官方动作槽'
    import_result=$(python3 "$install_dir/runtime.py" import-model "$2" "$3" "$4")
    model_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "$import_result")
    python3 "$install_dir/model_preflight.py" model-assign "$model_id" "$4"
    request_relax_service
    systemctl stop robotd.service
    python3 "$install_dir/runtime.py" assign-model "$model_id" "$4"
    restart_service
    verify_motion_models
    python3 "$install_dir/runtime.py" model-assignment "$model_id" "$4"
    ;;
pad-settings)
    require_installed
    [[ $# -eq 3 ]] || fail '用法：pad-settings 嘴巴百分比 头部幅度rad'
    python3 "$install_dir/gamepad.py" validate-settings "$2" "$3"
    python3 "$install_dir/gamepad.py" check-live-settings
    python3 "$install_dir/gamepad.py" save-settings "$2" "$3"
    python3 "$install_dir/gamepad.py" verify-settings
    echo '嘴巴与头部幅度已运行中更新；网页及真实手柄共同生效，未卸力或重启。'
    ;;
action-scale)
    require_installed
    [[ $# -eq 6 ]] || fail '用法：action-scale 模型标识 缩放 P D 转矩限制'
    python3 "$install_dir/runtime.py" validate-advanced "$3" "$4" "$5" "$6"
    # Applying numbers does not import or replace a model. Do not reparse all
    # training YAML or launch a second inference validator for this operation.
    request_relax_service
    systemctl stop robotd.service
    python3 "$install_dir/runtime.py" set-action-scale "$2" "$3" "$4" "$5" "$6"
    restart_service
    verify_motion_models
    echo "高级参数已应用：缩放 $3 / P $4 / D $5 / 转矩限制 $6；重新 HOME 上力后确认舵机寄存器。"
    ;;
model-delete)
    require_installed
    [[ $# -eq 2 ]] || fail '用法：model-delete 模型标识'
    # Preflight before any service or config mutation, including last-walk deletion.
    python3 "$install_dir/model_preflight.py" "$1" "$2"
    request_relax_service
    systemctl stop robotd.service
    python3 "$install_dir/runtime.py" delete-model "$2"
    restart_service
    verify_motion_models
    ;;

*)
    echo '用法：sudo bash service.sh {install|upgrade|status|connection|report|bus ...|enable|disable|init|enable-policy|disable-policy|relax|reconnect|models|power reboot/shutdown}' >&2
    exit 2
    ;;
esac
