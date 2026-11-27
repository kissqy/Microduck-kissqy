package com.microduck.phone.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import java.util.UUID

/**
 * 一条 BLE GATT 会话：扫描 → 连接 → 协商 MTU → 开通知 → 读版本 → 收发行。
 *
 * 这一层**不解释 JSON**，只搬字节（`Framer` 负责分块与拼行）。协议语义在
 * `RobotLink` 与页面的 `ble-bridge.js` 里，这样换传输时不用动它们。
 *
 * 两个写路径，对应两种完全不同的东西：
 *  * **有应答**：命令，排队、逐个写，慢但可靠（实测约 541 ms/帧）；
 *  * **无应答**：20 Hz 控制，不排队、失败就丢——下一帧 50 ms 后就来，重发旧的一帧
 *    只会让屏幕上的摇杆更迟。
 */
class BleClient(private val context: Context, private val listener: Listener) {

    interface Listener {
        fun onScan(name: String, address: String, rssi: Int, ipv4: String?)
        fun onLink(state: String, detail: String)
        fun onLine(line: String)
    }

    companion object {
        val SERVICE_UUID: UUID = UUID.fromString("6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019")
        val RPC_UUID: UUID = UUID.fromString("6f5d2a11-3b47-4c8e-9a1f-2d7e8c4b6019")
        private val CCCD_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        /** 广播里 IPv4 的公司 ID；真正的判别是设备广播了 SERVICE_UUID。 */
        private const val COMPANY_ID = 0xFFFF
        private const val REQUESTED_MTU = 517
    }

    /** 机器人读到的 `API_VERSION`；0 表示还没读到。 */
    @Volatile
    var apiVersion: Int = 0
        private set

    @Volatile
    var mtu: Int = 23
        private set
    private var gatt: BluetoothGatt? = null
    private var characteristic: BluetoothGattCharacteristic? = null
    private var scanning = false
    private val reassembler = Framer.Reassembler()
    private val outbound = ArrayDeque<ByteArray>()
    private var sending = false

    /** 最近一次链路状态与地址；页面切换时用来判断能否沿用现有 GATT。 */
    @Volatile
    private var linkState = "down"

    @Volatile
    private var linkAddress = ""

    private val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
    private val main = Handler(Looper.getMainLooper())

    /**
     * 所有状态回调都必须走这里。
     *
     * 页面之间的导航不会销毁 Activity，GATT 也应该一直活着；`connect()` 靠这里记下的
     * 状态判断是「新连接」还是「新页面接管旧连接」。
     */
    private fun emitLink(state: String, detail: String) {
        linkState = state
        listener.onLink(state, detail)
    }

    // ── 扫描 ────────────────────────────────────────────────────────────────

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val record = result.scanRecord
            val ipv4 = record?.getManufacturerSpecificData(COMPANY_ID)?.let(::decodeIpv4)
            val name = record?.deviceName ?: result.device.name ?: ""
            listener.onScan(name, result.device.address, result.rssi, ipv4)
        }

        override fun onScanFailed(errorCode: Int) {
            scanning = false
            emitLink("down", "扫描失败：error=$errorCode")
        }
    }

    @SuppressLint("MissingPermission")
    fun startScan(seconds: Long = 8) {
        if (scanning) return
        val scanner = adapter?.bluetoothLeScanner ?: run {
            emitLink("down", "这台设备没有 BLE")
            return
        }
        val filters = listOf(
            ScanFilter.Builder().setServiceUuid(ParcelUuid(SERVICE_UUID)).build(),
        )
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        scanning = true
        scanner.startScan(filters, settings, scanCallback)
        main.postDelayed({ stopScan() }, seconds * 1000)
    }

    @SuppressLint("MissingPermission")
    fun stopScan() {
        if (!scanning) return
        scanning = false
        adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        emitLink("idle", "扫描结束")
    }

    // ── 连接 ────────────────────────────────────────────────────────────────

    @SuppressLint("MissingPermission")
    fun connect(address: String) {
        stopScan()
        // 页面切换不会销毁 Activity：地址没变且链路还活着就直接沿用，只把当前状态
        // 回报给新页面。以前每次都 closeGatt() 重建，切一次页要多等 1–3 秒。
        if (gatt != null && address.equals(linkAddress, ignoreCase = true) &&
            (linkState == "ready" || linkState == "connected" || linkState == "connecting")
        ) {
            emitLink(linkState, if (linkState == "ready") "复用已有连接" else "继续连接")
            return
        }
        closeGatt()
        val device: BluetoothDevice = adapter?.getRemoteDevice(address) ?: run {
            emitLink("down", "没有蓝牙适配器")
            return
        }
        linkAddress = address
        emitLink("connecting", address)
        gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
    }

    @SuppressLint("MissingPermission")
    fun disconnect() {
        gatt?.disconnect()
        closeGatt()
        emitLink("down", "已断开")
    }

    private fun closeGatt() {
        characteristic = null
        apiVersion = 0
        mtu = 23
        reassembler.reset()
        synchronized(outbound) {
            outbound.clear()
            sending = false
        }
        gatt?.close()
        gatt = null
    }

    private val callback = object : BluetoothGattCallback() {

        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    emitLink("connected", "status=$status")
                    @SuppressLint("MissingPermission")
                    if (!gatt.discoverServices()) {
                        emitLink("down", "开始发现服务失败")
                    }
                }

                BluetoothProfile.STATE_DISCONNECTED -> {
                    closeGatt()
                    emitLink("down", "链路断开：status=$status")
                }
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            val service = gatt.getService(SERVICE_UUID)
            val char = service?.getCharacteristic(RPC_UUID)
            if (char == null) {
                emitLink("down", "机器人没有 RPC 特征（固件版本过旧？）")
                gatt.disconnect()
                return
            }
            characteristic = char
            // MTU 协商失败也会回调 onMtuChanged（status 非 0），所以在这里不分支：
            // 拿不到 517 就用默认 23，控制帧退化为排队写。
            @SuppressLint("MissingPermission")
            if (!gatt.requestMtu(REQUESTED_MTU)) {
                enableNotifications(gatt, char)
            }
        }

        override fun onMtuChanged(gatt: BluetoothGatt, mtu: Int, status: Int) {
            this@BleClient.mtu = if (status == BluetoothGatt.GATT_SUCCESS) mtu else 23
            val char = characteristic ?: return
            enableNotifications(gatt, char)
        }

        override fun onDescriptorWrite(
            gatt: BluetoothGatt,
            descriptor: BluetoothGattDescriptor,
            status: Int,
        ) {
            val char = characteristic ?: return
            readVersion(gatt, char)
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            char: BluetoothGattCharacteristic,
            value: ByteArray,
            status: Int,
        ) {
            finishRead(value)
        }

        /** Android 12 及以下的读回调，值在特征上。 */
        @Deprecated("Android 13 起用带 value 的重载")
        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            char: BluetoothGattCharacteristic,
            status: Int,
        ) {
            @Suppress("DEPRECATION")
            finishRead(char.value ?: ByteArray(0))
        }

        @Deprecated("Android 13 有带 value 的重载；旧的回调在 33+ 仍会到达")
        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            char: BluetoothGattCharacteristic,
        ) {
            val data = char.value ?: return
            for (line in reassembler.feed(data)) listener.onLine(line)
        }

        override fun onCharacteristicWrite(
            gatt: BluetoothGatt,
            char: BluetoothGattCharacteristic,
            status: Int,
        ) {
            synchronized(outbound) {
                sending = false
            }
            drain()
        }
    }

    @SuppressLint("MissingPermission")
    private fun enableNotifications(gatt: BluetoothGatt, char: BluetoothGattCharacteristic) {
        if (!gatt.setCharacteristicNotification(char, true)) {
            readVersion(gatt, char)
            return
        }
        val cccd = char.getDescriptor(CCCD_UUID)
        if (cccd == null) {
            readVersion(gatt, char)
            return
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            gatt.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
        } else {
            @Suppress("DEPRECATION")
            cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            @Suppress("DEPRECATION")
            gatt.writeDescriptor(cccd)
        }
    }

    private fun finishRead(value: ByteArray) {
        apiVersion = decodeApiVersion(value)
        emitLink("ready", "api=$apiVersion mtu=$mtu")
    }

    @SuppressLint("MissingPermission")
    private fun readVersion(gatt: BluetoothGatt, char: BluetoothGattCharacteristic) {
        if (!gatt.readCharacteristic(char)) {
            // 读不到版本不该挡住使用：协议内容没变，只是少了握手的版本号。
            emitLink("ready", "api=0（读版本失败）")
        }
    }

    // ── 写 ──────────────────────────────────────────────────────────────────

    /**
     * 写一行。`fast=true` 是不带应答的控制帧：不排队，一包发完，否则退回排队。
     *
     * @return 是否交给了链路层
     */
    @SuppressLint("MissingPermission")
    fun write(line: String, fast: Boolean): Boolean {
        val gatt = this.gatt ?: return false
        val char = characteristic ?: return false
        val chunks = Framer.chunk(line.toByteArray(Charsets.UTF_8), mtu - 3)
        if (chunks.isEmpty()) return false
        if (fast && chunks.size == 1) {
            return writeChunk(
                gatt,
                char,
                chunks[0],
                BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE,
            )
        }
        synchronized(outbound) {
            outbound.addAll(chunks)
        }
        drain()
        return true
    }

    @SuppressLint("MissingPermission")
    private fun drain() {
        val gatt = this.gatt ?: return
        val char = characteristic ?: return
        val next: ByteArray
        synchronized(outbound) {
            if (sending) return
            next = outbound.removeFirstOrNull() ?: return
            sending = true
        }
        if (!writeChunk(gatt, char, next, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)) {
            synchronized(outbound) {
                sending = false
                outbound.clear()
            }
        }
    }

    /**
     * 一次 GATT 写。Android 13 才有带 value 的重载，而 minSdk 是 26，所以两条路都要。
     */
    @SuppressLint("MissingPermission")
    private fun writeChunk(
        gatt: BluetoothGatt,
        char: BluetoothGattCharacteristic,
        data: ByteArray,
        writeType: Int,
    ): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            // 33 起这个重载返回 BluetoothStatusCodes，而不是 Boolean。
            return gatt.writeCharacteristic(char, data, writeType) ==
                android.bluetooth.BluetoothStatusCodes.SUCCESS
        }
        @Suppress("DEPRECATION")
        char.writeType = writeType
        @Suppress("DEPRECATION")
        char.value = data
        @Suppress("DEPRECATION")
        return gatt.writeCharacteristic(char)
    }

    private fun decodeIpv4(data: ByteArray): String? {
        if (data.size !in 4..5) return null
        val address = "${data[0].toInt() and 0xff}.${data[1].toInt() and 0xff}." +
            "${data[2].toInt() and 0xff}.${data[3].toInt() and 0xff}"
        return if (address == "0.0.0.0") null else address
    }
}

/**
 * 版本特征是**一个字节**（机器人侧 `API_VERSION as u8`，41 → `0x29`），不是十进制文本。
 *
 * 早先按文本 `toIntOrNull()` 解析，`0x28` 在 UTF-8 里是 `(`，于是永远读成 0——版本号
 * 看起来"没读到"，桥接就跳过了"固件太旧"的判断。文本形式只在手工调试时出现过，所以
 * 多字节时仍按文本兜底。
 */
internal fun decodeApiVersion(value: ByteArray): Int = when {
    value.isEmpty() -> 0
    value.size == 1 -> value[0].toInt() and 0xff
    else -> value.toString(Charsets.UTF_8).trim().toIntOrNull() ?: 0
}
