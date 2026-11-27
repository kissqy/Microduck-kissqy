package com.microduck.phone.ble

/**
 * 驾驶摇杆的夹限。放在 App 侧是**双保险**而不是替代：`robotd` 的安全层仍会限幅并回报
 * `limited_by`，这里只是保证页面抖一下不会把越界值写进 20 Hz 的流里。
 *
 * 数值来自 `duckphone-ble-plan.zh-CN.md` §3：vx ∈ [-0.25, 0.35]，vyaw ∈ [-0.8, 0.8]。
 */
object Limits {
    const val VX_MIN = -0.25
    const val VX_MAX = 0.35
    const val VYAW_MAX = 0.8

    data class Twist(val vx: Double, val vyaw: Double)

    fun clampTwist(vx: Double, vyaw: Double): Twist {
        val safeVx = if (vx.isFinite()) vx.coerceIn(VX_MIN, VX_MAX) else 0.0
        val safeVyaw = if (vyaw.isFinite()) vyaw.coerceIn(-VYAW_MAX, VYAW_MAX) else 0.0
        return Twist(safeVx, safeVyaw)
    }
}
