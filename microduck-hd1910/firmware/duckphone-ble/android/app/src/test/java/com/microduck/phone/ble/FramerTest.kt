package com.microduck.phone.ble

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FramerTest {

    private fun line(text: String) = (text + "\n").toByteArray(Charsets.UTF_8)

    @Test
    fun `a request is cut into mtu minus three chunks`() {
        val payload = line(
            "{\"jsonrpc\":\"2.0\",\"method\":\"robot.move\"," +
                "\"params\":{\"vx\":0.1,\"vy\":0,\"vyaw\":0.2}}",
        )
        val expected = (payload.size + 19) / 20
        val chunks = Framer.chunk(payload, 20)
        assertTrue("this fixture should span more than two chunks", expected > 2)
        assertEquals(expected, chunks.size)
        assertEquals(payload.size, chunks.sumOf { it.size })
        assertTrue(chunks.all { it.size <= 20 })
        assertEquals(payload.toList(), chunks.flatMap { it.toList() })
    }

    @Test
    fun `a tiny mtu still yields only complete chunks`() {
        val payload = line("{}")
        val chunks = Framer.chunk(payload, 1)
        assertEquals(1, chunks.size)
        assertEquals(payload.toList(), chunks[0].toList())
    }

    @Test
    fun `empty input has no chunks`() {
        assertTrue(Framer.chunk(ByteArray(0), 20).isEmpty())
    }

    @Test
    fun `a line split across notifications is reassembled`() {
        val reassembler = Framer.Reassembler()
        assertTrue(reassembler.feed("{\"method\":\"ro".toByteArray()).isEmpty())
        val lines = reassembler.feed("bot.state\"}\n".toByteArray())
        assertEquals(listOf("{\"method\":\"robot.state\"}"), lines)
    }

    @Test
    fun `several frames in one notification all come out`() {
        val reassembler = Framer.Reassembler()
        val lines = reassembler.feed("{\"a\":1}\n{\"b\":2}\n{\"c\"".toByteArray())
        assertEquals(listOf("{\"a\":1}", "{\"b\":2}"), lines)
        assertEquals(listOf("{\"c\":3}"), reassembler.feed(":3}\n".toByteArray()))
    }

    @Test
    fun `blank lines are ignored and reset drops the half line`() {
        val reassembler = Framer.Reassembler()
        assertTrue(reassembler.feed("\n\n".toByteArray()).isEmpty())
        reassembler.feed("{\"half\":".toByteArray())
        reassembler.reset()
        assertEquals(listOf("{\"whole\":1}"), reassembler.feed("{\"whole\":1}\n".toByteArray()))
    }
}
