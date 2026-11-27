package com.microduck.phone

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.microduck.phone.ble.BleClient
import com.microduck.phone.ble.RobotLink
import com.microduck.phone.web.JsBridge
import org.json.JSONObject

/**
 * 一个 WebView 加一条 BLE。
 *
 * 页面是 `firmware/duckphone/static/` 的只读副本，原样加载；传输层由
 * `ble-bridge.js` 在**文档开始前**注入，把页面的 WebSocket 换成本地桥——所以原网页版
 * 一行不改，副本也不用改。
 */
class MainActivity : Activity(), BleClient.Listener {

    companion object {
        private const val ASSET_HOST = "appassets.androidplatform.net"
        private const val START_URL = "https://$ASSET_HOST/assets/ble-connect.html"
        private const val PERMISSION_REQUEST = 7

        /**
         * 页面自己用的**根路径**资源（`/style.css`、`/app.js`、`/icon.svg`）。
         *
         * duckphone 的网页版挂在 `http://<机器人>:8001/`，所有资源都是绝对路径；App 里页面在
         * `/assets/duckphone/` 下，绝对路径会 404——早先主页面"布局坏了"其实就是 CSS 与
         * app.js 一个都没加载。页面文件不能改，所以在请求这一层把根路径映射到副本目录。
         */
        private const val ASSET_PREFIX = "/assets/duckphone"
    }

    private lateinit var webView: WebView
    private lateinit var assetLoader: WebViewAssetLoader
    private lateinit var ble: BleClient
    private lateinit var link: RobotLink
    private lateinit var bridge: JsBridge
    private val handler = Handler(Looper.getMainLooper())
    private var pendingBridgeScript: String? = null
    private var ready = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        WebView.setWebContentsDebuggingEnabled(BuildConfigCompat.debug)

        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.mediaPlaybackRequiresUserGesture = false
        }

        val loader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()
        assetLoader = loader

        ble = BleClient(this, this)
        link = RobotLink(
            send = { line -> ble.write(line, fast = isControlFrame(line)) },
            clock = HandlerClock(handler),
            onNotification = { line -> bridge.postNotify(line) },
        )
        bridge = JsBridge(
            webView = webView,
            ble = ble,
            link = link,
            keepScreenOn = { on -> setScreenOn(on) },
        )

        webView.addJavascriptInterface(bridge, "DuckNative")
        // 真机调试：页面的 console.* 与 JS 异常都进 logcat（`adb logcat -s DuckWeb`）。
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                Log.i("DuckWeb", "${message.message()} (${message.lineNumber()})")
                return true
            }
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest,
            ): WebResourceResponse? {
                val url = request.url
                if (url.host == ASSET_HOST && !url.path.orEmpty().startsWith("/assets/")) {
                    // 驾驶页的绝对路径（`/style.css` 等）→ 副本目录。
                    return assetLoader.shouldInterceptRequest(
                        Uri.parse("https://$ASSET_HOST$ASSET_PREFIX${url.path}"),
                    )
                }
                return assetLoader.shouldInterceptRequest(url)
            }

            override fun onPageStarted(view: WebView, url: String, favicon: android.graphics.Bitmap?) {
                pendingBridgeScript?.let { view.evaluateJavascript(it, null) }
            }
        }

        setContentView(webView)
        injectBridgeAtDocumentStart()
        requestBlePermissions()
        webView.loadUrl(START_URL)
    }

    /**
     * 把 `ble-bridge.js` 放在页面任何脚本之前。
     *
     * `DOCUMENT_START_SCRIPT` 是唯一可靠的时机：页面的 `app.js` 一执行就会
     * `new WebSocket(...)`，晚一步就只会在第一条消息上失败。老 WebView 退回
     * `onPageStarted`，页面自己的重连会补上。
     */
    private fun injectBridgeAtDocumentStart() {
        val script = assets.open("ble-bridge.js").bufferedReader().use { it.readText() }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            runCatching {
                WebViewCompat.addDocumentStartJavaScript(webView, script, setOf("*"))
                return
            }
        }
        pendingBridgeScript = script
    }

    // ── 权限 ────────────────────────────────────────────────────────────────

    private fun requiredPermissions(): Array<String> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }

    private fun requestBlePermissions() {
        val missing = requiredPermissions().filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            bridge.postPermission(true)
        } else {
            requestPermissions(missing.toTypedArray(), PERMISSION_REQUEST)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST) {
            bridge.postPermission(grantResults.all { it == PackageManager.PERMISSION_GRANTED })
        }
    }

    // ── BleClient.Listener（回调在 binder 线程）─────────────────────────────

    override fun onScan(name: String, address: String, rssi: Int, ipv4: String?) {
        bridge.postScan(name, address, rssi, ipv4)
    }

    override fun onLink(state: String, detail: String) {
        Log.i("DuckLink", "$state $detail")
        ready = state == "ready"
        if (!ready) setScreenOn(false)
        bridge.postLink(state, detail)
    }

    override fun onLine(line: String) {
        link.onLine(line)
    }

    // ── 生命周期与安全 ──────────────────────────────────────────────────────

    private fun isControlFrame(line: String): Boolean =
        !line.contains("\"id\"") &&
            (line.contains("\"robot.move\"") || line.contains("\"robot.head\""))

    private fun setScreenOn(on: Boolean) {
        handler.post {
            if (on) {
                window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            } else {
                window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
        }
    }

    /**
     * 切后台先归零再断开，不等 500 ms 的 deadman。
     *
     * 权限对话框也会触发 `onPause`，所以只在确实连上时做——否则第一次启动就被自己的
     * 授权流程踢下线。
     */
    override fun onPause() {
        super.onPause()
        if (!ready) return
        link.notify("robot.move", "{\"vx\":0,\"vy\":0,\"vyaw\":0}")
        handler.postDelayed({ ble.disconnect() }, 150)
    }

    override fun onDestroy() {
        ble.disconnect()
        link.failAll("应用退出")
        webView.destroy()
        super.onDestroy()
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    private class HandlerClock(private val handler: Handler) : RobotLink.Clock {
        override fun after(ms: Long, action: () -> Unit): () -> Unit {
            val runnable = Runnable(action)
            handler.postDelayed(runnable, ms)
            return { handler.removeCallbacks(runnable) }
        }
    }
}

/** `BuildConfig.DEBUG` 在 `applicationId` 之外也能用；单独包一层是为了这里不依赖生成类。 */
private object BuildConfigCompat {
    val debug: Boolean = runCatching {
        Class.forName("com.microduck.phone.BuildConfig")
            .getField("DEBUG")
            .getBoolean(null)
    }.getOrDefault(false)
}
