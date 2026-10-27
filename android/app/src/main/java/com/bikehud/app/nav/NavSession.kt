package com.bikehud.app.nav

import android.app.Activity
import android.util.Log
import com.bikehud.app.BikeHudApp
import com.bikehud.app.ble.NavPacket
import com.google.android.libraries.navigation.AudioGuidanceSettings
import com.google.android.libraries.navigation.NavigationApi
import com.google.android.libraries.navigation.Navigator
import com.google.android.libraries.navigation.RoutingOptions
import com.google.android.libraries.navigation.SimulationOptions
import com.google.android.libraries.navigation.Waypoint
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Owns the Navigation SDK navigator.
 *
 * COST: the only billed call in the app is setDestination() in start(). It runs only from the Start
 * button, at most once per tap, only when idle, and only if DailyCap allows it. No automatic retries.
 */
class NavSession(private val activity: Activity) {
    enum class Phase { LOADING, READY, ROUTING, NAVIGATING, ERROR }

    private val app = activity.application as BikeHudApp
    val cap = DailyCap(activity)

    private val _phase = MutableStateFlow(Phase.LOADING)
    val phase: StateFlow<Phase> = _phase

    private val _message = MutableStateFlow("")
    val message: StateFlow<String> = _message

    private var navigator: Navigator? = null
    private var voiceOn = false

    // shows Google's terms dialog the first time, needs location permission already granted
    fun init() {
        if (navigator != null) return
        NavigationApi.getNavigator(activity, object : NavigationApi.NavigatorListener {
            override fun onNavigatorReady(nav: Navigator) {
                navigator = nav
                nav.registerServiceForNavUpdates(activity.packageName, NavUpdatesService::class.java.name, 0)
                nav.addArrivalListener { onArrived() }
                applyAudio(nav)
                _phase.value = Phase.READY
            }

            override fun onError(errorCode: Int) {
                // e.g. NOT_AUTHORIZED = API key/restriction problem, TERMS_NOT_ACCEPTED
                Log.w(TAG, "navigator error $errorCode")
                _phase.value = Phase.ERROR
                _message.value = "Navigation SDK error $errorCode"
            }
        })
    }

    fun start(lat: Double, lng: Double, title: String, simulate: Boolean) {
        val nav = navigator ?: return
        if (_phase.value != Phase.READY) return  // blocks double taps while routing/navigating
        if (!cap.tryUse()) {
            _message.value = "Daily limit of ${DailyCap.MAX_DESTINATIONS_PER_DAY} routes reached"
            return
        }
        _phase.value = Phase.ROUTING
        _message.value = ""

        val destination = Waypoint.builder().setLatLng(lat, lng).setTitle(title).build()
        val options = RoutingOptions().travelMode(RoutingOptions.TravelMode.CYCLING)

        // BILLED: one Navigation Request (destination) per call
        nav.setDestination(destination, options).setOnResultListener { status ->
            if (status == Navigator.RouteStatus.OK) {
                if (simulate) {
                    nav.simulator.simulateLocationsAlongExistingRoute(SimulationOptions().speedMultiplier(1f))
                }
                nav.startGuidance()
                _phase.value = Phase.NAVIGATING
            } else {
                // no retry, user has to tap Start again
                _phase.value = Phase.READY
                _message.value = "Route failed: $status"
            }
        }
    }

    // SDK speaks directions by default, off unless the user turns it on (helmet shows the turns)
    fun setVoice(on: Boolean) {
        voiceOn = on
        navigator?.let { applyAudio(it) }
    }

    private fun applyAudio(nav: Navigator) {
        val mode = if (voiceOn) {
            AudioGuidanceSettings.GuidanceMode.VOICE_ALERTS_AND_GUIDANCE
        } else {
            AudioGuidanceSettings.GuidanceMode.SILENT
        }
        nav.setAudioGuidanceSettings(
            AudioGuidanceSettings.builder().setGuidanceMode(mode).setVibrationEnabled(false).build()
        )
    }

    fun stop() {
        val nav = navigator ?: return
        nav.stopGuidance()
        nav.clearDestinations()
        nav.simulator.unsetUserLocation()
        _phase.value = Phase.READY
        HudFeed.publish(app, HudCue.NONE)
    }

    private fun onArrived() {
        val nav = navigator ?: return
        HudFeed.publish(app, HudCue(NavPacket.TURN_ARRIVE, 0, "", 0))
        nav.stopGuidance()
        nav.clearDestinations()
        nav.simulator.unsetUserLocation()
        _phase.value = Phase.READY
        _message.value = "Arrived"
    }

    fun cleanup() {
        navigator?.let {
            it.stopGuidance()
            it.unregisterServiceForNavUpdates()
            it.cleanup()
        }
        navigator = null
    }

    companion object {
        private const val TAG = "NavSession"
    }
}
