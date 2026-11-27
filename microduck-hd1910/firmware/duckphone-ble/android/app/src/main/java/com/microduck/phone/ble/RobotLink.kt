package com.microduck.phone.ble

import org.json.JSONObject

/**
 * JSON-RPC 2.0 的请求/回答配对：id、超时、错误。
 *
 * 只管**一连接之内**的事：谁来写字节交给 `send`，时间从 `Clock` 来——这样 JVM 单元
 * 测试不需要 Android 的 Handler，也不需要真的等十秒。
 *
 * 通知（没有 `id` 的 `robot.state` 等）不参与配对，原样交给 `onNotification`。
 */
class RobotLink(
    private val send: (String) -> Unit,
    private val clock: Clock,
    private val timeoutMs: Long = 10_000,
    private val onNotification: (String) -> Unit = {},
) {

    /** 可注入的定时器。返回的函数取消这一次调度。 */
    interface Clock {
        fun after(ms: Long, action: () -> Unit): () -> Unit
    }

    sealed class Outcome {
        /** 成功，`result` 是 JSON 文本（可能是 `null`、对象或数组）。 */
        data class Ok(val result: String) : Outcome()

        /** 失败：`code` 是 JSON-RPC 错误码，链路问题时为 `null`。 */
        data class Err(val code: Int?, val message: String) : Outcome()
    }

    private class Pending(val callback: (Outcome) -> Unit) {
        var cancel: () -> Unit = {}
    }

    private val pending = mutableMapOf<Int, Pending>()
    private var nextId = 1

    /** 发一个请求，返回它的 id。回答（或超时）时回调一次。 */
    @Synchronized
    fun call(
        method: String,
        params: String,
        timeoutMs: Long = this.timeoutMs,
        callback: (Outcome) -> Unit,
    ): Int {
        val id = nextId++
        val payload = JSONObject()
            .put("jsonrpc", "2.0")
            .put("id", id)
            .put("method", method)
            .put("params", if (params.isBlank()) JSONObject() else JSONObject(params))
            .toString() + "\n"
        val entry = Pending(callback)
        // 先入表再排超时：一个 0 ms 的定时器不该在请求登记之前就把它判死。
        pending[id] = entry
        entry.cancel = clock.after(timeoutMs) {
            take(id)?.callback?.invoke(Outcome.Err(null, "请求超时：$method"))
        }
        send(payload)
        return id
    }

    /** 发一个通知：没有 `id`，也就没有回答。控制流走这里。 */
    fun notify(method: String, params: String) {
        val payload = JSONObject()
            .put("jsonrpc", "2.0")
            .put("method", method)
            .put("params", if (params.isBlank()) JSONObject() else JSONObject(params))
            .toString() + "\n"
        send(payload)
    }

    /** 喂一行收到的 JSON。配对上的回答交给它的回调，其余按通知处理。 */
    fun onLine(line: String) {
        val message = runCatching { JSONObject(line) }.getOrNull() ?: return
        val hasId = message.has("id") && !message.isNull("id")
        if (!hasId) {
            if (message.optString("method", "").isNotEmpty()) onNotification(line)
            return
        }
        val id = message.optInt("id", -1)
        val entry = take(id) ?: return
        val error = message.optJSONObject("error")
        if (error != null) {
            entry.callback(
                Outcome.Err(error.optInt("code"), error.optString("message", "未知错误")),
            )
        } else {
            entry.callback(Outcome.Ok(message.opt("result")?.toString() ?: "null"))
        }
    }

    /** 链路断开：所有在等的请求立刻失败，而不是各自等满超时。 */
    @Synchronized
    fun failAll(reason: String) {
        val waiting = pending.values.toList()
        pending.clear()
        waiting.forEach {
            it.cancel()
            it.callback(Outcome.Err(null, reason))
        }
    }

    @Synchronized
    private fun take(id: Int): Pending? {
        val entry = pending.remove(id) ?: return null
        entry.cancel()
        return entry
    }
}
