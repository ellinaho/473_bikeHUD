package com.bikehud.app.nav

import com.bikehud.app.ble.NavPacket
import com.google.android.libraries.mapsplatform.turnbyturn.model.Maneuver

/**
 * Navigation SDK maneuver -> our packet turn type (see nav/README.md, Maneuver to Turn Type).
 * Anything not listed (straight, depart, name change, ferry, unknown) is sent as straight.
 */
object ManeuverMap {
    fun toTurnType(maneuver: Int): Int = when (maneuver) {
        Maneuver.TURN_LEFT -> NavPacket.TURN_LEFT
        Maneuver.TURN_RIGHT -> NavPacket.TURN_RIGHT

        Maneuver.TURN_SLIGHT_LEFT, Maneuver.TURN_KEEP_LEFT -> NavPacket.TURN_SLIGHT_LEFT
        Maneuver.TURN_SLIGHT_RIGHT, Maneuver.TURN_KEEP_RIGHT -> NavPacket.TURN_SLIGHT_RIGHT

        Maneuver.TURN_SHARP_LEFT -> NavPacket.TURN_SHARP_LEFT
        Maneuver.TURN_SHARP_RIGHT -> NavPacket.TURN_SHARP_RIGHT

        Maneuver.TURN_U_TURN_CLOCKWISE, Maneuver.TURN_U_TURN_COUNTERCLOCKWISE,
        Maneuver.ON_RAMP_U_TURN_CLOCKWISE, Maneuver.ON_RAMP_U_TURN_COUNTERCLOCKWISE,
        Maneuver.OFF_RAMP_U_TURN_CLOCKWISE, Maneuver.OFF_RAMP_U_TURN_COUNTERCLOCKWISE -> NavPacket.TURN_UTURN

        in Maneuver.ROUNDABOUT_CLOCKWISE..Maneuver.ROUNDABOUT_EXIT_COUNTERCLOCKWISE -> NavPacket.TURN_ROUNDABOUT

        Maneuver.DESTINATION, Maneuver.DESTINATION_LEFT, Maneuver.DESTINATION_RIGHT -> NavPacket.TURN_ARRIVE

        Maneuver.FORK_LEFT -> NavPacket.TURN_FORK_LEFT
        Maneuver.FORK_RIGHT -> NavPacket.TURN_FORK_RIGHT

        Maneuver.MERGE_UNSPECIFIED, Maneuver.MERGE_LEFT, Maneuver.MERGE_RIGHT -> NavPacket.TURN_MERGE

        Maneuver.ON_RAMP_LEFT, Maneuver.ON_RAMP_KEEP_LEFT, Maneuver.ON_RAMP_SLIGHT_LEFT, Maneuver.ON_RAMP_SHARP_LEFT,
        Maneuver.OFF_RAMP_LEFT, Maneuver.OFF_RAMP_KEEP_LEFT, Maneuver.OFF_RAMP_SLIGHT_LEFT,
        Maneuver.OFF_RAMP_SHARP_LEFT -> NavPacket.TURN_RAMP_LEFT

        Maneuver.ON_RAMP_RIGHT, Maneuver.ON_RAMP_KEEP_RIGHT, Maneuver.ON_RAMP_SLIGHT_RIGHT, Maneuver.ON_RAMP_SHARP_RIGHT,
        Maneuver.OFF_RAMP_RIGHT, Maneuver.OFF_RAMP_KEEP_RIGHT, Maneuver.OFF_RAMP_SLIGHT_RIGHT,
        Maneuver.OFF_RAMP_SHARP_RIGHT -> NavPacket.TURN_RAMP_RIGHT

        else -> NavPacket.TURN_STRAIGHT
    }
}
