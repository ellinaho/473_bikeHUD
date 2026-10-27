package com.bikehud.app.ble

import java.util.UUID

/**
 * Nav packet format sent to the helmet, must match nav/nav_packet.py on the Pi.
 * Layout (little endian): version u8, turn u8, dist_m u16, remaining_m u16, name_len u8, name UTF-8
 */
object NavPacket {
    val SERVICE_UUID: UUID = UUID.fromString("e92011aa-4b4e-452d-ba3a-33271a383755")
    val CHAR_UUID: UUID = UUID.fromString("6b16fa29-fdf4-4eed-a96a-3fc13b8d85db")

    const val VERSION = 1
    const val HEADER_SIZE = 7
    const val MAX_NAME_BYTES = 40

    // turn types, add new ones at the end so old numbers keep their meaning
    const val TURN_NONE = 0
    const val TURN_STRAIGHT = 1
    const val TURN_LEFT = 2
    const val TURN_RIGHT = 3
    const val TURN_SLIGHT_LEFT = 4
    const val TURN_SLIGHT_RIGHT = 5
    const val TURN_SHARP_LEFT = 6
    const val TURN_SHARP_RIGHT = 7
    const val TURN_UTURN = 8
    const val TURN_ROUNDABOUT = 9
    const val TURN_ARRIVE = 10
    const val TURN_FORK_LEFT = 11
    const val TURN_FORK_RIGHT = 12
    const val TURN_MERGE = 13
    const val TURN_RAMP_LEFT = 14
    const val TURN_RAMP_RIGHT = 15

    fun turnName(turn: Int): String = when (turn) {
        TURN_NONE -> "none"
        TURN_STRAIGHT -> "straight"
        TURN_LEFT -> "left"
        TURN_RIGHT -> "right"
        TURN_SLIGHT_LEFT -> "slight left"
        TURN_SLIGHT_RIGHT -> "slight right"
        TURN_SHARP_LEFT -> "sharp left"
        TURN_SHARP_RIGHT -> "sharp right"
        TURN_UTURN -> "u-turn"
        TURN_ROUNDABOUT -> "roundabout"
        TURN_ARRIVE -> "arrive"
        TURN_FORK_LEFT -> "fork left"
        TURN_FORK_RIGHT -> "fork right"
        TURN_MERGE -> "merge"
        TURN_RAMP_LEFT -> "ramp left"
        TURN_RAMP_RIGHT -> "ramp right"
        else -> "turn $turn"
    }

    /**
     * - builds a packet, distances clamped to 0..65535 m
     * - street name cut to maxNameBytes without splitting a UTF-8 character
     */
    fun pack(turn: Int, dist: Int, street: String, remaining: Int = 0, maxNameBytes: Int = MAX_NAME_BYTES): ByteArray {
        val name = truncateUtf8(street, maxNameBytes.coerceIn(0, MAX_NAME_BYTES))
        val d = dist.coerceIn(0, 0xFFFF)
        val r = remaining.coerceIn(0, 0xFFFF)

        val out = ByteArray(HEADER_SIZE + name.size)
        out[0] = VERSION.toByte()
        out[1] = turn.toByte()
        out[2] = (d and 0xFF).toByte()
        out[3] = (d shr 8).toByte()
        out[4] = (r and 0xFF).toByte()
        out[5] = (r shr 8).toByte()
        out[6] = name.size.toByte()
        name.copyInto(out, HEADER_SIZE)
        return out
    }

    private fun truncateUtf8(s: String, maxBytes: Int): ByteArray {
        val bytes = s.toByteArray(Charsets.UTF_8)
        if (bytes.size <= maxBytes) return bytes
        // back up while the cut lands on a continuation byte (10xxxxxx)
        var end = maxBytes
        while (end > 0 && (bytes[end].toInt() and 0xC0) == 0x80) end--
        return bytes.copyOf(end)
    }
}
