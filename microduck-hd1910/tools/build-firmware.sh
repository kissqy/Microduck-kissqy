#!/usr/bin/env bash
# Portable local build of the R17 v1.0.146 Zero programs. Never deploys a robot.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/firmware"
BUILD_DIR="$REPO_ROOT/.build/firmware"
TOOLS_DIR="$REPO_ROOT/.build/firmware-tools"
RUST_VERSION=1.99.0
CARGO_ZIGBUILD_VERSION=0.23.4
ZIG_VERSION=0.14.1
RUST_TARGET=aarch64-unknown-linux-gnu
ZIGBUILD_TARGET=aarch64-unknown-linux-gnu.2.31

usage() {
  cat <<'EOF'
用法：bash tools/build-firmware.sh [--help | --check]

无参数    下载并校验两份固定版本的 ARM64 libudev 开发依赖，然后编译。
--check   只检查本机工具、Rust 目标和固定依赖记录；不下载、不编译、不创建目录。
--help    显示本说明。

输出：.build/firmware/bin/
      robotd、robotctl、padd、sounds、gamesir-xboxd
      BUILD-LOCAL.json、SHA256SUMS

环境：Linux / Windows WSL，Rust 1.99.0、cargo-zigbuild 0.23.4、Zig 0.14.1。
安装步骤见 docs/BUILD.md。脚本优先使用 .build/firmware-tools Python 环境。
本入口不调用 sudo、不安装系统软件、不连接机器人、不安装或发布固件。
EOF
}

MODE=build
case "${1:-}" in
  "") ;;
  --help|-h) usage; exit 0 ;;
  --check) MODE=check ;;
  *) usage >&2; exit 2 ;;
esac
if (( $# > 1 )); then usage >&2; exit 2; fi

export PYTHONDONTWRITEBYTECODE=1
if [[ -x "$TOOLS_DIR/bin/python" ]]; then
  export PATH="$TOOLS_DIR/bin:$PATH"
  PYTHON_BIN="$TOOLS_DIR/bin/python"
else
  PYTHON_BIN="$(command -v python3 || true)"
fi
ZIG_BIN=
RUSTC_BIN=
FAILURES=0

fail_check() {
  printf '缺少或不匹配：%s\n' "$1" >&2
  FAILURES=$((FAILURES + 1))
}

check_requirements() {
  local tool installed version sysroot
  [[ "$(uname -s)" == Linux ]] || fail_check '请在 Linux 或 WSL 的 Linux 终端执行。'
  for tool in rustup cargo-zigbuild cc pkg-config dpkg-deb readelf; do
    command -v "$tool" >/dev/null 2>&1 || fail_check "$tool"
  done
  [[ -n "$PYTHON_BIN" ]] || fail_check 'python3'
  for tool in Cargo.toml Cargo.lock rust-toolchain.toml gamepad-r7/gamesir-xboxd.c verification/native-dependencies146.json; do
    [[ -f "$SOURCE_DIR/$tool" ]] || fail_check "firmware/$tool"
  done

  if command -v rustup >/dev/null 2>&1; then
    installed="$(rustup toolchain list 2>/dev/null || true)"
    if [[ "$installed" =~ (^|[[:space:]])1\.99\.0(-|[[:space:]]|$) ]]; then
      # Check an already installed toolchain. Do not ask rustup to install anything.
      RUSTC_BIN="$(rustup which --toolchain "$RUST_VERSION" rustc 2>/dev/null || true)"
      if [[ -x "$RUSTC_BIN" ]]; then
        version="$("$RUSTC_BIN" --version)"
        [[ "$version" == "rustc $RUST_VERSION "* ]] || fail_check "Rust $RUST_VERSION"
        sysroot="$("$RUSTC_BIN" --print sysroot)"
        [[ -d "$sysroot/lib/rustlib/$RUST_TARGET/lib" ]] || fail_check "Rust target $RUST_TARGET"
        printf '%s\n' "$version"
      else
        fail_check "Rust $RUST_VERSION 的 rustc 程序"
      fi
    else
      fail_check "Rust $RUST_VERSION（检查时不会自动安装）"
    fi
  fi
  if command -v cargo-zigbuild >/dev/null 2>&1; then
    version="$(cargo-zigbuild --version 2>/dev/null || true)"
    [[ "$version" == "cargo-zigbuild $CARGO_ZIGBUILD_VERSION" ]] || fail_check "cargo-zigbuild $CARGO_ZIGBUILD_VERSION"
    printf '%s\n' "${version:-cargo-zigbuild 无法启动}"
  fi
  if [[ -n "$PYTHON_BIN" ]]; then
    # find_spec locates the wheel without importing its executable entry point.
    ZIG_BIN="$("$PYTHON_BIN" -c 'import importlib.util,pathlib; s=importlib.util.find_spec("ziglang"); print(pathlib.Path(s.origin).resolve().parent / "zig" if s and s.origin else "")' 2>/dev/null || true)"
  fi
  if [[ ! -x "$ZIG_BIN" ]]; then ZIG_BIN="$(command -v zig || true)"; fi
  if [[ -x "$ZIG_BIN" ]]; then
    version="$("$ZIG_BIN" version 2>/dev/null || true)"
    [[ "$version" == "$ZIG_VERSION" ]] || fail_check "Zig $ZIG_VERSION"
    printf 'Zig %s\n' "${version:-无法启动}"
  else
    fail_check "Zig $ZIG_VERSION（可安装 ziglang Python 包）"
  fi
  if command -v pkg-config >/dev/null 2>&1; then
    if ! env -u PKG_CONFIG_SYSROOT_DIR -u PKG_CONFIG_LIBDIR -u PKG_CONFIG_PATH pkg-config --exists libudev; then
      fail_check '宿主机 libudev-dev；它与待下载的 ARM64 libudev 是两套依赖。'
    fi
  fi
  # External flags can bypass Zig or change the release profile without notice.
  for tool in RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER CARGO_PROFILE_RELEASE_CODEGEN_UNITS; do
    [[ -z "${!tool:-}" ]] || fail_check "外部 $tool 已设置；请在干净终端运行，或先 unset $tool。"
  done
  if [[ -n "$PYTHON_BIN" && -f "$SOURCE_DIR/verification/native-dependencies146.json" ]]; then
    if ! "$PYTHON_BIN" - "$SOURCE_DIR/verification/native-dependencies146.json" <<'PY'
import json, pathlib, sys
record = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "libudev-dev": ("247.3-7+deb11u5", "608eecca1c50230a5488ce436e30926f3b93c57ed018fd7318f1fd278070bdef"),
    "libudev1": ("247.3-7+deb11u5", "df88275dafcc3b0759ef03d5027fa1f90f48bf7aeec461887798bd18298fe799"),
}
found = {p["package"]: p for g in record["groups"] if g["architecture"] == "arm64" for p in g["packages"]}
if set(found) != set(expected):
    raise SystemExit("ARM64 依赖清单与 v146 不一致。")
for name, (version, digest) in expected.items():
    item = found[name]
    url = f"https://deb.debian.org/debian/pool/main/s/systemd/{name}_{version}_arm64.deb"
    if (item["version"], item["sha256"], item["url"], item["architecture"]) != (version, digest, url, "arm64"):
        raise SystemExit(f"{name} 的版本、来源或 SHA256 与 v146 不一致。")
print("ARM64 libudev 固定版本、下载地址和 SHA256 记录一致。")
PY
    then fail_check '固定 ARM64 依赖记录'; fi
  fi
  (( FAILURES == 0 ))
}

if ! check_requirements; then
  printf '\n请按 docs/BUILD.md 安装所需工具，再执行 --check。\n' >&2
  exit 1
fi
if [[ "$MODE" == check ]]; then
  printf '\n依赖检查通过。没有下载依赖或执行编译。\n'
  exit 0
fi

mkdir -p "$BUILD_DIR/bin"
"$PYTHON_BIN" - "$SOURCE_DIR/verification/native-dependencies146.json" "$BUILD_DIR" <<'PY'
import hashlib, json, pathlib, subprocess, sys, urllib.request
record = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
root = pathlib.Path(sys.argv[2])
cache = root / "downloads"
sysroot = root / "sysroot/arm64"
cache.mkdir(parents=True, exist_ok=True)
sysroot.mkdir(parents=True, exist_ok=True)
packages = [p for g in record["groups"] if g["architecture"] == "arm64" for p in g["packages"]]
for item in packages:
    path = cache / item["url"].rsplit("/", 1)[1]
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".part")
        try:
            print(f"下载固定依赖：{item['package']} {item['version']}", flush=True)
            with urllib.request.urlopen(item["url"], timeout=45) as response, temporary.open("wb") as target:
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != item["sha256"]:
                raise SystemExit(f"SHA256 校验失败：{path.name}；已停止，未使用该文件。")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise SystemExit(f"缓存文件校验失败：{path}；请检查或移走该缓存后重试。")
    subprocess.run(["dpkg-deb", "--extract", str(path), str(sysroot)], check=True)
(root / "arm64-dependencies.json").write_text(json.dumps(packages, indent=2) + "\n", encoding="utf-8")
PY

export CARGO_TARGET_DIR="$BUILD_DIR/target"
export CARGO_ZIGBUILD_ZIG_PATH="$ZIG_BIN"
export CARGO_ZIGBUILD_PYTHON_PATH="$PYTHON_BIN"
export PKG_CONFIG_ALLOW_CROSS=1
export PKG_CONFIG_SYSROOT_DIR="$BUILD_DIR/sysroot/arm64"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_SYSROOT_DIR/usr/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_SYSROOT_DIR/usr/share/pkgconfig"
unset PKG_CONFIG_PATH
pkg-config --exists libudev
(
  cd -- "$SOURCE_DIR"
  rustup run "$RUST_VERSION" cargo zigbuild --locked --release \
    --target "$ZIGBUILD_TARGET" -p robotd -p robotctl -p padd -p sounds
)
"$ZIG_BIN" cc -target aarch64-linux-gnu.2.31 -O2 -Wall -Wextra -Werror \
  -std=gnu11 "$SOURCE_DIR/gamepad-r7/gamesir-xboxd.c" -o "$BUILD_DIR/bin/gamesir-xboxd"
for program in robotd robotctl padd sounds; do
  cp -- "$CARGO_TARGET_DIR/$RUST_TARGET/release/$program" "$BUILD_DIR/bin/$program"
done

"$PYTHON_BIN" - "$SOURCE_DIR" "$BUILD_DIR/bin" <<'PY'
import datetime, hashlib, json, os, pathlib, re, subprocess, sys
source, output = map(pathlib.Path, sys.argv[1:])
programs = ["robotd", "robotctl", "padd", "sounds", "gamesir-xboxd"]
records = {}
for name in programs:
    path = output / name
    env = {**os.environ, "LC_ALL": "C"}
    header = subprocess.check_output(["readelf", "-h", str(path)], text=True, env=env)
    versions = subprocess.check_output(["readelf", "--version-info", str(path)], text=True, env=env)
    glibc = sorted(set(re.findall(r"GLIBC_(\d+\.\d+)", versions)), key=lambda s: tuple(map(int, s.split("."))))
    if "AArch64" not in header or not glibc or tuple(map(int, glibc[-1].split("."))) > (2, 31):
        raise SystemExit(f"ELF 架构或 GLIBC 符号检查失败：{name}")
    records[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
                     "architecture": "AArch64", "glibc_versions": glibc}
manifest = {
    "kind": "local-source-build", "source_version": "R17-v1.0.146",
    "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "rust": "1.99.0", "cargo_zigbuild": "0.23.4", "zig": "0.14.1",
    "target": "aarch64-unknown-linux-gnu.2.31", "programs": records,
    "hardware_tested": False, "automatically_deployed": False,
    "byte_identical_to_published_release_claimed": False,
    "verification": "ELF architecture, GLIBC symbol floor and SHA256; no unit tests or hardware tests run by this script",
}
(output / "BUILD-LOCAL.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
(output / "SHA256SUMS").write_text("".join(f"{records[n]['sha256']}  {n}\n" for n in programs), encoding="utf-8")
print(f"完成：{output}")
PY
