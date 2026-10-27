package com.bikehud.app

import android.Manifest
import android.location.Geocoder
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.bikehud.app.ble.HudBle
import com.bikehud.app.ble.NavPacket
import com.bikehud.app.nav.HudCue
import com.bikehud.app.nav.HudFeed
import com.bikehud.app.nav.NavSession
import com.bikehud.app.ui.theme.BikeHUDTheme
import com.google.android.libraries.navigation.NavigationView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

class MainActivity : ComponentActivity() {
    private lateinit var nav: NavSession

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        nav = NavSession(this)
        val ble = (application as BikeHudApp).ble
        enableEdgeToEdge()
        setContent {
            BikeHUDTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    MainScreen(ble, nav, lifecycle, Modifier.padding(innerPadding))
                }
            }
        }
    }

    override fun onDestroy() {
        // app closed by the user, end the ride and drop the helmet link
        if (isFinishing) {
            nav.cleanup()
            (application as BikeHudApp).ble.disconnect()
        }
        super.onDestroy()
    }
}

private val startupPermissions = buildList {
    add(Manifest.permission.ACCESS_FINE_LOCATION)
    if (Build.VERSION.SDK_INT >= 31) {
        add(Manifest.permission.BLUETOOTH_SCAN)
        add(Manifest.permission.BLUETOOTH_CONNECT)
    }
    if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
}.toTypedArray()

private data class Place(val lat: Double, val lng: Double, val label: String)

@Composable
private fun MainScreen(ble: HudBle, nav: NavSession, lifecycle: Lifecycle, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    val bleState by ble.state.collectAsState()
    val phase by nav.phase.collectAsState()
    val navMessage by nav.message.collectAsState()
    val cue by HudFeed.cue.collectAsState()

    var address by remember { mutableStateOf("") }
    var place by remember { mutableStateOf<Place?>(null) }
    var simulate by remember { mutableStateOf(false) }
    var voice by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("") }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        if (results[Manifest.permission.ACCESS_FINE_LOCATION] == true) {
            nav.init()
        } else {
            status = "Location permission is needed for navigation"
        }
    }
    LaunchedEffect(Unit) { permissionLauncher.launch(startupPermissions) }

    Column(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        // helmet link
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Helmet: $bleState", Modifier.weight(1f))
            if (bleState == HudBle.State.CONNECTED || bleState == HudBle.State.CONNECTING) {
                OutlinedButton(onClick = { ble.disconnect() }) { Text("Disconnect") }
            } else {
                Button(onClick = { ble.connect() }) { Text("Connect") }
            }
            OutlinedButton(onClick = { ble.forget() }) { Text("Forget") }
        }

        // destination, Find is free (Android Geocoder), only Start is billed
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = address,
                onValueChange = { address = it; place = null },
                label = { Text("Destination address") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Button(
                enabled = address.isNotBlank(),
                onClick = {
                    scope.launch {
                        place = geocode(context, address)
                        status = if (place == null) "Address not found" else ""
                    }
                },
            ) { Text("Find") }
        }
        place?.let { Text("Going to: ${it.label}", style = MaterialTheme.typography.bodySmall) }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                enabled = place != null && phase == NavSession.Phase.READY && nav.cap.remaining > 0,
                onClick = { place?.let { nav.start(it.lat, it.lng, it.label, simulate) } },
            ) { Text("Start") }
            OutlinedButton(
                enabled = phase == NavSession.Phase.NAVIGATING,
                onClick = { nav.stop() },
            ) { Text("Stop") }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = simulate, onCheckedChange = { simulate = it }, enabled = phase == NavSession.Phase.READY)
            Text("Simulate ride")
            Checkbox(checked = voice, onCheckedChange = { voice = it; nav.setVoice(it) })
            Text("Voice")
        }

        Text("Nav: $phase   Routes left today: ${nav.cap.remaining}/${com.bikehud.app.nav.DailyCap.MAX_DESTINATIONS_PER_DAY}")
        Text("Helmet shows: ${cueText(cue)}", style = MaterialTheme.typography.titleMedium)
        listOf(status, navMessage).filter { it.isNotEmpty() }.forEach { Text(it, color = MaterialTheme.colorScheme.error) }

        // Google's navigation map, only once the navigator is ready (after terms + location permission)
        if (phase != NavSession.Phase.LOADING && phase != NavSession.Phase.ERROR) {
            NavMap(lifecycle, Modifier.fillMaxWidth().weight(1f))
        }
    }
}

// Android's built-in geocoder, not a billed Google Maps API
private suspend fun geocode(context: android.content.Context, address: String): Place? = withContext(Dispatchers.IO) {
    if (!Geocoder.isPresent()) return@withContext null
    try {
        @Suppress("DEPRECATION")
        val result = Geocoder(context).getFromLocationName(address, 1)?.firstOrNull() ?: return@withContext null
        Place(result.latitude, result.longitude, result.getAddressLine(0) ?: address)
    } catch (e: Exception) {
        null
    }
}

private fun cueText(cue: HudCue): String {
    if (cue.turn == NavPacket.TURN_NONE) return "nothing"
    val street = if (cue.street.isNotEmpty()) " onto ${cue.street}" else ""
    return "${NavPacket.turnName(cue.turn)} in ${imperial(cue.dist)}$street"
}

// same rule as the helmet: feet under 0.1 mi, then miles
private fun imperial(meters: Int): String {
    val miles = meters / 1609.344
    return if (miles < 0.1) "${(meters * 3.28084).roundToInt()} ft" else "%.1f mi".format(miles)
}

// NavigationView needs the activity lifecycle forwarded to it
@Composable
private fun NavMap(lifecycle: Lifecycle, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val view = remember { NavigationView(context).also { it.onCreate(null) } }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> view.onStart()
                Lifecycle.Event.ON_RESUME -> view.onResume()
                Lifecycle.Event.ON_PAUSE -> view.onPause()
                Lifecycle.Event.ON_STOP -> view.onStop()
                else -> {}
            }
        }
        lifecycle.addObserver(observer)
        onDispose {
            lifecycle.removeObserver(observer)
            if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) view.onPause()
            if (lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) view.onStop()
            view.onDestroy()
        }
    }
    AndroidView(factory = { view }, modifier = modifier)
}
