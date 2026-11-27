package com.microduck.phone.ble

import org.junit.Assert.assertEquals
import org.junit.Test

class LimitsTest {

    @Test
    fun `inside the range passes through`() {
        val twist = Limits.clampTwist(0.2, -0.5)
        assertEquals(0.2, twist.vx, 1e-9)
        assertEquals(-0.5, twist.vyaw, 1e-9)
    }

    @Test
    fun `the edges are the documented ones`() {
        assertEquals(Limits.VX_MIN, Limits.clampTwist(-9.0, 0.0).vx, 1e-9)
        assertEquals(Limits.VX_MAX, Limits.clampTwist(9.0, 0.0).vx, 1e-9)
        assertEquals(Limits.VYAW_MAX, Limits.clampTwist(0.0, 9.0).vyaw, 1e-9)
        assertEquals(-Limits.VYAW_MAX, Limits.clampTwist(0.0, -9.0).vyaw, 1e-9)
    }

    @Test
    fun `a non-finite axis becomes zero rather than a wild value`() {
        val twist = Limits.clampTwist(Double.NaN, Double.POSITIVE_INFINITY)
        assertEquals(0.0, twist.vx, 1e-9)
        assertEquals(0.0, twist.vyaw, 1e-9)
    }
}
