package com.bikehud.app.nav

import com.bikehud.app.ble.NavPacket
import com.google.android.libraries.mapsplatform.turnbyturn.model.Maneuver
import org.junit.Assert.assertEquals
import org.junit.Test

// pure mapping tests, no Navigation SDK calls
class ManeuverMapTest {
    private fun turn(m: Int) = ManeuverMap.toTurnType(m)

    @Test
    fun basicTurns() {
        assertEquals(NavPacket.TURN_LEFT, turn(Maneuver.TURN_LEFT))
        assertEquals(NavPacket.TURN_RIGHT, turn(Maneuver.TURN_RIGHT))
        assertEquals(NavPacket.TURN_SLIGHT_LEFT, turn(Maneuver.TURN_KEEP_LEFT))
        assertEquals(NavPacket.TURN_SHARP_RIGHT, turn(Maneuver.TURN_SHARP_RIGHT))
        assertEquals(NavPacket.TURN_UTURN, turn(Maneuver.TURN_U_TURN_COUNTERCLOCKWISE))
    }

    @Test
    fun groups() {
        assertEquals(NavPacket.TURN_ROUNDABOUT, turn(Maneuver.ROUNDABOUT_CLOCKWISE))
        assertEquals(NavPacket.TURN_ROUNDABOUT, turn(Maneuver.ROUNDABOUT_EXIT_COUNTERCLOCKWISE))
        assertEquals(NavPacket.TURN_ARRIVE, turn(Maneuver.DESTINATION_RIGHT))
        assertEquals(NavPacket.TURN_MERGE, turn(Maneuver.MERGE_LEFT))
        assertEquals(NavPacket.TURN_RAMP_LEFT, turn(Maneuver.OFF_RAMP_SLIGHT_LEFT))
        assertEquals(NavPacket.TURN_RAMP_RIGHT, turn(Maneuver.ON_RAMP_KEEP_RIGHT))
        assertEquals(NavPacket.TURN_UTURN, turn(Maneuver.OFF_RAMP_U_TURN_CLOCKWISE))
    }

    @Test
    fun everythingElseIsStraight() {
        for (m in listOf(Maneuver.UNKNOWN, Maneuver.DEPART, Maneuver.STRAIGHT, Maneuver.NAME_CHANGE,
                Maneuver.FERRY_BOAT, Maneuver.ON_RAMP_UNSPECIFIED, 999)) {
            assertEquals(NavPacket.TURN_STRAIGHT, turn(m))
        }
    }
}
