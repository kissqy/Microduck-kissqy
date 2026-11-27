package com.microduck.phone.ble

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RobotLinkTest {

    /** 手动时钟：测试自己决定超时什么时候发生，而不是等十秒。 */
    private class ManualClock : RobotLink.Clock {
        private val tasks = mutableListOf<Pair<Long, () -> Unit>>()

        override fun after(ms: Long, action: () -> Unit): () -> Unit {
            val task = ms to action
            tasks += task
            return { tasks.remove(task) }
        }

        fun fire() {
            val due = tasks.toList()
            tasks.clear()
            due.forEach { it.second() }
        }

        fun pendingCount(): Int = tasks.size
    }

    private val sent = mutableListOf<String>()
    private val notifications = mutableListOf<String>()
    private val clock = ManualClock()

    private fun link() = RobotLink(
        send = { line -> sent += line },
        clock = clock,
        timeoutMs = 10_000,
        onNotification = { line -> notifications += line },
    )

    @Test
    fun `a call is one jsonrpc line with the next id`() {
        val link = link()
        val first = link.call("robot.stop", "") {}
        val second = link.call("robot.init", "{}") {}
        assertEquals(1, first)
        assertEquals(2, second)

        val request = JSONObject(sent[0])
        assertEquals("2.0", request.getString("jsonrpc"))
        assertEquals(1, request.getInt("id"))
        assertEquals("robot.stop", request.getString("method"))
        assertEquals(0, request.getJSONObject("params").length())
        assertTrue(sent[0].endsWith("\n"))
    }

    @Test
    fun `a notification carries no id and no timeout`() {
        val link = link()
        link.notify("robot.move", "{\"vx\":0.1,\"vy\":0,\"vyaw\":0}")
        val request = JSONObject(sent[0])
        assertTrue(!request.has("id"))
        assertEquals(0, clock.pendingCount())
    }

    @Test
    fun `the answer with the matching id is delivered and cancels the timeout`() {
        val link = link()
        var result: RobotLink.Outcome? = null
        link.call("robot.health", "{}") { result = it }
        link.onLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"healthy\":true}}")

        val ok = result as RobotLink.Outcome.Ok
        assertTrue(JSONObject(ok.result).getBoolean("healthy"))
        assertEquals(0, clock.pendingCount())
    }

    @Test
    fun `an unmatched id is ignored`() {
        val link = link()
        var result: RobotLink.Outcome? = null
        link.call("robot.health", "{}") { result = it }
        link.onLine("{\"jsonrpc\":\"2.0\",\"id\":99,\"result\":{}}")
        assertNull(result)
        assertEquals(1, clock.pendingCount())
    }

    @Test
    fun `an error answer carries its code and message`() {
        val link = link()
        var result: RobotLink.Outcome? = null
        link.call("robot.relax", "{}") { result = it }
        link.onLine(
            "{\"jsonrpc\":\"2.0\",\"id\":1," +
                "\"error\":{\"code\":-32601,\"message\":\"not available\"}}",
        )
        val err = result as RobotLink.Outcome.Err
        assertEquals(-32601, err.code)
        assertEquals("not available", err.message)
    }

    @Test
    fun `the clock firing turns a silent request into a timeout`() {
        val link = link()
        var result: RobotLink.Outcome? = null
        link.call("robot.stop", "{}") { result = it }
        clock.fire()
        val err = result as RobotLink.Outcome.Err
        assertNull(err.code)
        assertTrue(err.message, err.message.contains("超时"))
    }

    @Test
    fun `a state frame is a notification, not a missing answer`() {
        val link = link()
        var result: RobotLink.Outcome? = null
        link.call("robot.subscribe", "{}") { result = it }
        link.onLine("{\"jsonrpc\":\"2.0\",\"method\":\"robot.state\",\"params\":{\"t\":1}}")
        assertNull(result)
        assertEquals(1, notifications.size)
        assertTrue(notifications[0].contains("robot.state"))
    }

    @Test
    fun `a broken link fails everything waiting`() {
        val link = link()
        val outcomes = mutableListOf<RobotLink.Outcome>()
        link.call("robot.stop", "{}") { outcomes += it }
        link.call("robot.init", "{}") { outcomes += it }
        link.failAll("链路断开")

        assertEquals(2, outcomes.size)
        assertTrue(outcomes.all { it is RobotLink.Outcome.Err && it.message == "链路断开" })
        assertEquals(0, clock.pendingCount())
    }
}
