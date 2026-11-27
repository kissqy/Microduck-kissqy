#!/usr/bin/env bash
# 构建 APK，并把产物拷到 microduck-hd1910/.build/apk/。
#
# 需要 Android SDK（platform 35 / build-tools 35）和 JDK 21。SDK 路径按顺序取：
#   $ANDROID_HOME → $ANDROID_SDK_ROOT → ~/Android/Sdk
#
# 用法：
#   bash build_apk.sh              # assembleDebug
#   bash build_apk.sh --release    # assembleRelease（读 android/keystore.properties 签名）
#   bash build_apk.sh --check      # 只检查环境，不构建
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$HERE/../android"
OUT_DIR="$HERE/../../../.build/apk"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"

die() { printf '\033[31m[err]\033[0m %s\n' "$*" >&2; exit 2; }

[[ -d "$ANDROID_DIR" ]] || die "找不到 Android 工程：$ANDROID_DIR"
[[ -x "$ANDROID_DIR/gradlew" ]] || die "缺少 gradlew；Gradle wrapper 需要随工程一起提交"
if [[ ! -f "$ANDROID_DIR/gradle/wrapper/gradle-wrapper.jar" ]] && ! command -v gradle >/dev/null; then
  die "没有 Gradle：装好 Gradle 8.9 后在 android/ 里跑一次 'gradle wrapper'（会生成 wrapper jar）"
fi
[[ -d "$SDK" ]] || die "找不到 Android SDK：$SDK（装好后设置 ANDROID_HOME，或放到 ~/Android/Sdk）"
[[ -d "$SDK/platforms/android-35" ]] || die "SDK 里没有 android-35；用 sdkmanager 安装 platform 35"
[[ -d "$SDK/build-tools/35.0.0" ]] || echo "[warn] 没看到 build-tools 35.0.0；Gradle 可能自行下载"
command -v java >/dev/null || die "没有 java；需要 JDK 21"

export ANDROID_HOME="$SDK"
export ANDROID_SDK_ROOT="$SDK"
export PATH="$SDK/platform-tools:$PATH"

[[ "${1:-}" == "--check" ]] && { echo "环境检查通过：$SDK"; exit 0; }

VARIANT="debug"
[[ "${1:-}" == "--release" ]] && VARIANT="release"

if [[ "$VARIANT" == "release" ]]; then
  if [[ -f "$ANDROID_DIR/keystore.properties" ]]; then
    echo "== 构建发布 APK（keystore.properties 签名）"
  else
    echo "[warn] 没有 android/keystore.properties，release 产物将未签名（不能直接安装）"
  fi
  TASK="assembleRelease"
  APK="$ANDROID_DIR/app/build/outputs/apk/release/app-release-unsigned.apk"
  [[ -f "$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk" ]] && APK="$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk"
else
  echo "== 构建调试 APK"
  TASK="assembleDebug"
  APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
fi

( cd "$ANDROID_DIR" && ./gradlew --no-daemon "$TASK" )

[[ -f "$APK" ]] || die "构建结束但没找到 $APK"
mkdir -p "$OUT_DIR"
TARGET="$OUT_DIR/duckphone-ble-$VARIANT-$(date +%Y%m%d-%H%M).apk"
cp -- "$APK" "$TARGET"
echo "APK：$TARGET"
echo "安装：bash $HERE/install_apk.sh $TARGET"
