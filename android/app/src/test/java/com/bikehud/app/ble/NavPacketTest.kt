package com.bikehud.app.ble

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

// pure packet tests, no BLE or Google API calls
class NavPacketTest {
    private fun hex(s: String) = s.split(" ").map { it.toInt(16).toByte() }.toByteArray()

    @Test
    fun matchesReadmeExample() {
        val p = NavPacket.pack(NavPacket.TURN_LEFT, 150, "State St", 1200)
        assertArrayEquals(hex("01 02 96 00 B0 04 08 53 74 61 74 65 20 53 74"), p)
    }

    @Test
    fun clampsDistances() {
        val p = NavPacket.pack(NavPacket.TURN_RIGHT, 99999, "", -5)
        assertEquals(0xFF.toByte(), p[2])
        assertEquals(0xFF.toByte(), p[3])
        assertEquals(0.toByte(), p[4])
        assertEquals(0.toByte(), p[5])
    }

    @Test
    fun truncatesNameWithoutSplittingChars() {
        // é is 2 bytes, 30 of them = 60 bytes, cut to 40 = 20 chars
        val p = NavPacket.pack(NavPacket.TURN_LEFT, 10, "é".repeat(30))
        assertEquals(40, p[6].toInt())
        assertEquals("é".repeat(20), String(p, NavPacket.HEADER_SIZE, 40, Charsets.UTF_8))

        // odd limit lands mid-character, backs up to 38
        val q = NavPacket.pack(NavPacket.TURN_LEFT, 10, "é".repeat(30), maxNameBytes = 39)
        assertEquals(38, q[6].toInt())
    }
}
