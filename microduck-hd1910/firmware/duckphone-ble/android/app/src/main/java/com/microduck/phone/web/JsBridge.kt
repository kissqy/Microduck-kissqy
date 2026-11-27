package com.microduck.phone.web

import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.microduck.phone.ble.BleClient
import com.microduck.phone.ble.RobotLink
import org.json.JSONObject

/**
 * 页面与原生之间的唯一接口。
 *
 * 分工是刻意的：**Kotlin 只做传输**（BLE、JSON-RPC 配对、超时），页面协议（`hello` /
 * `state` / `cmd`）在 `ble-bridge.js` 里翻译。这样页面逻辑可以脱离 Android 单测，
 * 换传输（比如 WebRTC）时也不用重写 UI。
 *
 * JS 侧：
 *  * `DuckNative.call(method, paramsJson)` → 返回请求 id，回答经 `onResult(id, ok, payload)`；
 *  * `DuckNative.notify(method, paramsJson)` → 无回答；
 *  * `DuckNative.scan()` / `connect(address)` / `disconnect()`；
 *  * 原生回推：`DuckNativeBridge.onResult / onScan / onLink / onNotify / onPermission`。
 */
class JsBridge(
    private val webView: WebView,
    private val ble: BleClient,
    private val link: RobotLink,
    private val keepScreenOn: (Boolean) -> Unit,
) {

    /**
     * 发一个 JSON-RPC 请求，返回请求 id。
     *
     * `timeoutMs` 为 0 用默认 10 s；`net.connect` 这类要几十秒的调用自己传。
     */
    @JavascriptInterface
    fun call(method: String, params: String, timeoutMs: Int): Int {
        var requestId = 0
        requestId = link.call(
            method,
            params,
            timeoutMs = if (timeoutMs > 0) timeoutMs.toLong() else 10_000,
        ) { outcome ->
            Log.i("DuckRpc", "← $method ${describe(outcome)}")
            postResult(requestId, outcome)
        }
        Log.i("DuckRpc", "→ $method #$requestId")
        return requestId
    }

    private fun describe(outcome: RobotLink.Outcome): String = when (outcome) {
        is RobotLink.Outcome.Ok -> "ok ${outcome.result.take(120)}"
        is RobotLink.Outcome.Err -> "err ${outcome.message}"
    }

    @JavascriptInterface
    fun notify(method: String, params: String) {
        link.notify(method, params)
    }

    @JavascriptInterface
    fun scan() {
        ble.startScan()
    }

    @JavascriptInterface
    fun connect(address: String) {
        ble.connect(address)
    }

    @JavascriptInterface
    fun disconnect() {
        ble.disconnect()
    }

    @JavascriptInterface
    fun info(): String = JSONObject()
        .put("apiVersion", ble.apiVersion)
        .put("mtu", ble.mtu)
        .toString()

    @JavascriptInterface
    fun keepScreen(on: Boolean) {
        keepScreenOn(on)
    }

    // ── 原生 → 页面 ─────────────────────────────────────────────────────────

    fun postResult(id: Int, outcome: RobotLink.Outcome) {
        val ok = outcome is RobotLink.Outcome.Ok
        if (!ok) Log.w("DuckLink", "rpc $id 失败：${(outcome as RobotLink.Outcome.Err).message}")
        val payload = when (outcome) {
            is RobotLink.Outcome.Ok -> outcome.result
            is RobotLink.Outcome.Err -> JSONObject()
                .put("code", outcome.code ?: JSONObject.NULL)
                .put("message", outcome.message)
                .toString()
        }
        eval("window.DuckNativeBridge&&DuckNativeBridge.onResult($id,$ok,${quote(payload)})")
    }

    fun postScan(name: String, address: String, rssi: Int, ipv4: String?) {
        val payload = JSONObject()
            .put("name", name)
            .put("address", address)
            .put("rssi", rssi)
            .put("ipv4", ipv4 ?: JSONObject.NULL)
            .toString()
        eval("window.DuckNativeBridge&&DuckNativeBridge.onScan(${quote(payload)})")
    }

    fun postLink(state: String, detail: String) {
        eval(
            "window.DuckNativeBridge&&DuckNativeBridge.onLink(" +
                "${quote(state)},${quote(detail)})",
        )
    }

    fun postNotify(line: String) {
        eval("window.DuckNativeBridge&&DuckNativeBridge.onNotify(${quote(line)})")
    }

    fun postPermission(granted: Boolean) {
        eval("window.DuckNativeBridge&&DuckNativeBridge.onPermission($granted)")
    }

    private fun eval(js: String) {
        webView.post { webView.evaluateJavascript(js, null) }
    }

    private fun quote(value: String): String = JSONObject.quote(value)
}
