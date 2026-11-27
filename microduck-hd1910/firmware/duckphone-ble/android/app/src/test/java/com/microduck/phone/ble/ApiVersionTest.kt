package com.microduck.phone.ble

import org.junit.Assert.assertEquals
import org.junit.Test

class ApiVersionTest {

    /** 机器人的版本特征是一个字节：41 → 0x29。按文本解析会读成 `)` 然后变成 0。 */
    @Test
    fun `a single byte is the version`() {
        assertEquals(41, decodeApiVersion(byteArrayOf(0x29)))
        assertEquals(40, decodeApiVersion(byteArrayOf(0x28)))
        assertEquals(0, decodeApiVersion(byteArrayOf(0x00)))
    }

    /** 手工调试时机器人回过十进制文本，这条兜底还在。 */
    @Test
    fun `decimal text still parses`() {
        assertEquals(41, decodeApiVersion("41".toByteArray()))
        assertEquals(41, decodeApiVersion(" 41 ".toByteArray()))
    }

    @Test
    fun `nothing read means no version`() {
        assertEquals(0, decodeApiVersion(ByteArray(0)))
        assertEquals(0, decodeApiVersion("abc".toByteArray()))
    }
}
