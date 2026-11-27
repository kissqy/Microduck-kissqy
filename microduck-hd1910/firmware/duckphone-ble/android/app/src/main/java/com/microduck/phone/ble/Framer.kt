package com.microduck.phone.ble

/**
 * 分块与重组，单独放这里是为了能在 JVM 上直接测。
 *
 * 协议：NDJSON，一行一条 JSON；请求按 `MTU-3` 切，回答/通知由 `btd` 按
 * `min(MTU-3, 512)` 切。切块本身没有长度前缀——接收侧只认 `\n`。
 */
object Framer {

    /** 一包能带的字节数下限：BLE 默认 MTU 23，减去 3 字节 ATT 头。 */
    const val MIN_CHUNK = 20

    /** 把一行（含结尾 `\n`）按 `chunk` 切开。空输入返回空列表。 */
    fun chunk(payload: ByteArray, chunk: Int): List<ByteArray> {
        if (payload.isEmpty()) return emptyList()
        val size = chunk.coerceAtLeast(MIN_CHUNK)
        return (payload.indices step size).map { start ->
            payload.copyOfRange(start, minOf(start + size, payload.size))
        }
    }

    /**
     * 收通知并拼回整行。
     *
     * 一个连接一个实例：半行状态属于连接，不属于某一次调用。
     */
    class Reassembler {
        private var pending = ByteArray(0)

        /** 喂一段通知，返回其中已经完整的行（不含换行符）。 */
        fun feed(data: ByteArray): List<String> {
            if (data.isEmpty()) return emptyList()
            pending += data
            val lines = mutableListOf<String>()
            var newline = pending.indexOf('\n'.code.toByte())
            while (newline >= 0) {
                val line = pending.copyOfRange(0, newline).toString(Charsets.UTF_8)
                pending = pending.copyOfRange(newline + 1, pending.size)
                if (line.isNotBlank()) lines += line
                newline = pending.indexOf('\n'.code.toByte())
            }
            return lines
        }

        /** 复位（断开连接时调用），丢掉半行。 */
        fun reset() {
            pending = ByteArray(0)
        }
    }
}
