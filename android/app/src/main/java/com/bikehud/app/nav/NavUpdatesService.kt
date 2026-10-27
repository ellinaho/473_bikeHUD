package com.bikehud.app.nav

import android.app.Service
import android.content.Intent
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.util.Log
import com.bikehud.app.BikeHudApp
import com.bikehud.app.ble.NavPacket
import com.google.android.libraries.mapsplatform.turnbyturn.TurnByTurnManager
import com.google.android.libraries.mapsplatform.turnbyturn.model.NavInfo
import com.google.android.libraries.mapsplatform.turnbyturn.model.NavState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

// what the helmet is currently showing, also shown in the app UI
data class HudCue(val turn: Int, val dist: Int, val street: String, val remaining: Int) {
    companion object {
        val NONE = HudCue(NavPacket.TURN_NONE, 0, "", 0)
    }
}

object HudFeed {
    private val _cue = MutableStateFlow(HudCue.NONE)
    val cue: StateFlow<HudCue> = _cue

    // sends to the helmet and updates the UI, safe to call when BLE is disconnected
    fun publish(app: BikeHudApp, cue: HudCue) {
        _cue.value = cue
        app.ble.send(cue.turn, cue.dist, cue.street, cue.remaining)
    }
}

/**
 * Bound by the Navigation SDK's turn-by-turn data feed (registerServiceForNavUpdates).
 * The SDK sends a NavInfo about once a second during guidance, each one is converted to a packet.
 * No Google API calls are made here.
 */
class NavUpdatesService : Service() {
    private lateinit var turnByTurnManager: TurnByTurnManager
    private lateinit var messenger: Messenger

    override fun onCreate() {
        super.onCreate()
        turnByTurnManager = TurnByTurnManager.createInstance()
        messenger = Messenger(IncomingHandler(Looper.getMainLooper()))
    }

    override fun onBind(intent: Intent?): IBinder = messenger.binder

    private inner class IncomingHandler(looper: Looper) : Handler(looper) {
        override fun handleMessage(msg: Message) {
            if (msg.what == TurnByTurnManager.MSG_NAV_INFO) {
                onNavInfo(turnByTurnManager.readNavInfoFromBundle(msg.data))
            }
        }
    }

    private fun onNavInfo(info: NavInfo) {
        val last = HudFeed.cue.value
        val cue = when (info.navState) {
            NavState.ENROUTE -> {
                val step = info.currentStep
                if (step != null) {
                    // raw SDK fields, for checking what the road name fields really contain
                    Log.d(TAG, "maneuver=${step.maneuver} simple='${step.simpleRoadName}' " +
                        "full='${step.fullRoadName}' instruction='${step.fullInstructionText}'")
                }
                if (step == null) {
                    last
                } else {
                    HudCue(
                        turn = ManeuverMap.toTurnType(step.maneuver),
                        dist = info.distanceToCurrentStepMeters ?: 0,
                        street = step.simpleRoadName ?: step.fullRoadName ?: "",
                        remaining = info.distanceToFinalDestinationMeters ?: 0,
                    )
                }
            }
            // no new route yet, keep showing the last turn
            NavState.REROUTING -> last
            // keep "arrive" up after the SDK ends guidance, otherwise clear the helmet
            NavState.STOPPED -> if (last.turn == NavPacket.TURN_ARRIVE) last.copy(dist = 0) else HudCue.NONE
            else -> last
        }
        HudFeed.publish(application as BikeHudApp, cue)
    }

    companion object {
        private const val TAG = "NavUpdates"
    }
}
