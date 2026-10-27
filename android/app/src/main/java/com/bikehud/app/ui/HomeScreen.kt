package com.bikehud.app.ui

import android.Manifest
import android.content.Context
import android.location.Geocoder
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.bikehud.app.R
import com.bikehud.app.ble.HudBle
import com.bikehud.app.ble.NavPacket
import com.bikehud.app.nav.DailyCap
import com.bikehud.app.nav.HudCue
import com.bikehud.app.nav.HudFeed
import com.bikehud.app.nav.NavSession
import com.bikehud.app.ui.theme.Apricot
import com.bikehud.app.ui.theme.ApricotSoft
import com.bikehud.app.ui.theme.Blush
import com.bikehud.app.ui.theme.BlushSoft
import com.bikehud.app.ui.theme.CardWhite
import com.bikehud.app.ui.theme.Coral
import com.bikehud.app.ui.theme.CoralSoft
import com.bikehud.app.ui.theme.DuskBlue
import com.bikehud.app.ui.theme.InkBlack
import com.bikehud.app.ui.theme.LavenderGrey
import com.bikehud.app.ui.theme.Mint
import com.bikehud.app.ui.theme.MintSoft
import com.bikehud.app.ui.theme.Mist
import com.bikehud.app.ui.theme.PrussianBlue
import com.google.android.libraries.navigation.NavigationView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

private val startupPermissions = buildList {
    add(Manifest.permission.ACCESS_FINE_LOCATION)
    if (Build.VERSION.SDK_INT >= 31) {
        add(Manifest.permission.BLUETOOTH_SCAN)
        add(Manifest.permission.BLUETOOTH_CONNECT)
    }
    if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
}.toTypedArray()

private data class Place(val lat: Double, val lng: Double, val label: String)

private val CardShape = RoundedCornerShape(24.dp)
private val ApricotDeep = Color(0xFFB8621F)   // readable apricot text on soft apricot

@Composable
fun HomeScreen(ble: HudBle, nav: NavSession, lifecycle: Lifecycle, modifier: Modifier = Modifier) {
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

    Column(
        modifier.fillMaxSize().padding(horizontal = 18.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        val subtitle = when (phase) {
            NavSession.Phase.LOADING -> "Getting ready"
            NavSession.Phase.ERROR -> "Navigation unavailable"
            NavSession.Phase.ROUTING -> "Finding your route"
            NavSession.Phase.NAVIGATING -> "Riding to ${place?.label?.substringBefore(",") ?: "your destination"}"
            NavSession.Phase.READY -> "Ready to ride"
        }
        Header(bleState, subtitle, onConnect = { ble.connect() }, onDisconnect = { ble.disconnect() }, onForget = { ble.forget() })

        TurnCard(cue, phase)

        // destination, Find is free (Android Geocoder), only Start is billed
        WhiteCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AppIcon(R.drawable.ic_location_on, Apricot, 20.dp)
                Spacer(Modifier.width(6.dp))
                Text("Destination", style = MaterialTheme.typography.titleSmall, color = PrussianBlue)
            }
            Spacer(Modifier.height(10.dp))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextField(
                    value = address,
                    onValueChange = { address = it; place = null },
                    placeholder = { Text("Address, like 1101 Beal Ave", color = LavenderGrey) },
                    leadingIcon = { AppIcon(R.drawable.ic_search, LavenderGrey, 20.dp) },
                    singleLine = true,
                    shape = RoundedCornerShape(16.dp),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Mist,
                        unfocusedContainerColor = Mist,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                        cursorColor = Apricot,
                    ),
                    modifier = Modifier.weight(1f),
                )
                Button(
                    enabled = address.isNotBlank(),
                    onClick = {
                        scope.launch {
                            place = geocode(context, address)
                            status = if (place == null) "Couldn't find that address" else ""
                        }
                    },
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = DuskBlue, contentColor = CardWhite),
                    modifier = Modifier.height(56.dp),
                ) { Text("Find") }
            }
            place?.let {
                Spacer(Modifier.height(10.dp))
                Pill(MintSoft) {
                    AppIcon(R.drawable.ic_check_circle, Color(0xFF2F7D5B), 16.dp)
                    Spacer(Modifier.width(6.dp))
                    Text(
                        it.label,
                        color = Color(0xFF2F7D5B),
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Button(
                enabled = place != null && phase == NavSession.Phase.READY && nav.cap.remaining > 0,
                onClick = { place?.let { nav.start(it.lat, it.lng, it.label, simulate) } },
                shape = CircleShape,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Apricot,
                    contentColor = CardWhite,
                    disabledContainerColor = ApricotSoft,
                    disabledContentColor = CardWhite,
                ),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 3.dp),
                modifier = Modifier.weight(1f).height(56.dp),
            ) {
                AppIcon(R.drawable.ic_navigation, CardWhite, 20.dp)
                Spacer(Modifier.width(8.dp))
                Text(
                    if (phase == NavSession.Phase.ROUTING) "Finding a route…" else "Start ride",
                    fontSize = 17.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
            }
            if (phase == NavSession.Phase.NAVIGATING) {
                Button(
                    onClick = { nav.stop() },
                    shape = CircleShape,
                    colors = ButtonDefaults.buttonColors(containerColor = CoralSoft, contentColor = Coral),
                    modifier = Modifier.height(56.dp),
                ) {
                    AppIcon(R.drawable.ic_stop, Coral, 20.dp)
                    Spacer(Modifier.width(4.dp))
                    Text("Stop", fontWeight = FontWeight.ExtraBold)
                }
            }
        }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Toggle("Simulate", R.drawable.ic_science, simulate, enabled = phase == NavSession.Phase.READY) { simulate = it }
            Toggle("Voice", if (voice) R.drawable.ic_volume_up else R.drawable.ic_volume_off, voice) { voice = it; nav.setVoice(it) }
            Spacer(Modifier.weight(1f))
            RidesToday(used = DailyCap.MAX_DESTINATIONS_PER_DAY - nav.cap.remaining)
        }

        listOf(status, navMessage).filter { it.isNotEmpty() }.forEach {
            Pill(CoralSoft) { Text(it, color = Coral, style = MaterialTheme.typography.bodySmall) }
        }

        // Google's navigation map, only once the navigator is ready (after terms + location permission)
        if (phase != NavSession.Phase.LOADING && phase != NavSession.Phase.ERROR) {
            Surface(
                color = CardWhite,
                shape = CardShape,
                shadowElevation = 2.dp,
                modifier = Modifier.fillMaxWidth().weight(1f),
            ) {
                NavMap(lifecycle, Modifier.fillMaxSize().padding(6.dp).clip(RoundedCornerShape(20.dp)))
            }
        }
    }
}

@Composable
private fun WhiteCard(content: @Composable ColumnScope.() -> Unit) {
    Surface(color = CardWhite, shape = CardShape, shadowElevation = 2.dp, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), content = content)
    }
}

@Composable
private fun Pill(color: Color, content: @Composable RowScope.() -> Unit) {
    Row(
        Modifier.background(color, RoundedCornerShape(14.dp)).padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

// Material Symbols Rounded drawables (res/drawable/ic_*), license: android/app/MATERIAL_SYMBOLS_LICENSE.txt
@Composable
private fun AppIcon(res: Int, tint: Color, size: Dp) {
    Icon(painterResource(res), contentDescription = null, tint = tint, modifier = Modifier.size(size))
}

@Composable
private fun Header(
    state: HudBle.State,
    subtitle: String,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onForget: () -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }
    data class Look(val icon: Int, val tint: Color, val bg: Color, val label: String)
    val look = when (state) {
        HudBle.State.CONNECTED -> Look(R.drawable.ic_bluetooth_connected, Mint, MintSoft, "Helmet on")
        HudBle.State.CONNECTING -> Look(R.drawable.ic_bluetooth_searching, Apricot, ApricotSoft, "Connecting")
        HudBle.State.SCANNING -> Look(R.drawable.ic_bluetooth_searching, Apricot, ApricotSoft, "Searching")
        HudBle.State.NOT_FOUND -> Look(R.drawable.ic_bluetooth_disabled, Coral, CoralSoft, "Not found")
        HudBle.State.BLUETOOTH_OFF -> Look(R.drawable.ic_bluetooth_disabled, Coral, CoralSoft, "Bluetooth off")
        HudBle.State.NO_PERMISSION -> Look(R.drawable.ic_bluetooth_disabled, Coral, CoralSoft, "Allow Bluetooth")
        HudBle.State.DISCONNECTED -> Look(R.drawable.ic_bluetooth, LavenderGrey, CardWhite, "Connect helmet")
    }

    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) {
        // app badge
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier.size(44.dp).background(Apricot, RoundedCornerShape(14.dp)),
        ) {
            AppIcon(R.drawable.ic_directions_bike, CardWhite, 26.dp)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text("BikeHUD", fontSize = 22.sp, fontWeight = FontWeight.Black, color = PrussianBlue)
            Text(subtitle, color = LavenderGrey, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Box {
            Surface(
                color = look.bg,
                shape = CircleShape,
                shadowElevation = 1.dp,
                onClick = {
                    val linked = state == HudBle.State.CONNECTED || state == HudBle.State.CONNECTING
                    if (linked) menuOpen = true else onConnect()
                },
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 9.dp),
                ) {
                    AppIcon(look.icon, look.tint, 18.dp)
                    Spacer(Modifier.width(6.dp))
                    Text(look.label, color = PrussianBlue, style = MaterialTheme.typography.labelLarge)
                }
            }
            DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                DropdownMenuItem(text = { Text("Disconnect") }, onClick = { menuOpen = false; onDisconnect() })
                DropdownMenuItem(text = { Text("Forget helmet") }, onClick = { menuOpen = false; onForget() })
            }
        }
    }
}

// what the helmet is showing right now, the colorful hero card
@Composable
private fun TurnCard(cue: HudCue, phase: NavSession.Phase) {
    val active = cue.turn != NavPacket.TURN_NONE
    val heading = when (phase) {
        NavSession.Phase.LOADING -> "GETTING READY"
        NavSession.Phase.ERROR -> "NAVIGATION UNAVAILABLE"
        NavSession.Phase.ROUTING -> "FINDING ROUTE"
        NavSession.Phase.NAVIGATING -> "NEXT TURN"
        NavSession.Phase.READY -> if (active) "NEXT TURN" else "READY WHEN YOU ARE"
    }
    val onCard = Color.White

    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(28.dp))
            .background(Brush.linearGradient(listOf(DuskBlue, LavenderGrey)))
            .padding(20.dp)
    ) {
        Column {
            Box(Modifier.background(onCard.copy(alpha = 0.18f), CircleShape).padding(horizontal = 10.dp, vertical = 4.dp)) {
                Text(heading, color = onCard, style = MaterialTheme.typography.labelSmall, letterSpacing = 1.2.sp)
            }
            Spacer(Modifier.height(14.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    contentAlignment = Alignment.Center,
                    modifier = Modifier.size(78.dp).background(onCard, CircleShape),
                ) {
                    AppIcon(turnIcon(cue.turn), if (active) Apricot else DuskBlue, 44.dp)
                }
                Spacer(Modifier.width(16.dp))
                Column(Modifier.weight(1f)) {
                    if (active) {
                        Text(
                            if (cue.turn == NavPacket.TURN_ARRIVE) "You've arrived" else imperial(cue.dist),
                            fontSize = if (cue.turn == NavPacket.TURN_ARRIVE) 26.sp else 38.sp,
                            fontWeight = FontWeight.Black,
                            color = onCard,
                        )
                        val sub = listOf(NavPacket.turnName(cue.turn).replaceFirstChar { it.uppercase() }, cue.street)
                            .filter { it.isNotEmpty() }
                            .joinToString(" · ")
                        Text(sub, color = onCard.copy(alpha = 0.9f), fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    } else {
                        Text("Where are we riding today?", fontSize = 21.sp, fontWeight = FontWeight.ExtraBold, color = onCard)
                        Text("Search for a destination below", color = onCard.copy(alpha = 0.9f))
                    }
                }
            }
            if (active && cue.remaining > 0) {
                Spacer(Modifier.height(14.dp))
                Row(
                    Modifier.background(onCard.copy(alpha = 0.18f), CircleShape).padding(horizontal = 12.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    AppIcon(R.drawable.ic_sports_score, onCard, 16.dp)
                    Spacer(Modifier.width(6.dp))
                    Text("${imperial(cue.remaining)} left", color = onCard, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

@Composable
private fun Toggle(label: String, icon: Int, selected: Boolean, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    FilterChip(
        selected = selected,
        onClick = { onChange(!selected) },
        enabled = enabled,
        label = { Text(label) },
        leadingIcon = { AppIcon(icon, if (selected) ApricotDeep else LavenderGrey, 18.dp) },
        shape = CircleShape,
        border = null,
        colors = FilterChipDefaults.filterChipColors(
            containerColor = CardWhite,
            labelColor = PrussianBlue,
            selectedContainerColor = ApricotSoft,
            selectedLabelColor = ApricotDeep,
        ),
    )
}

// little progress bar for the daily route cap
@Composable
private fun RidesToday(used: Int) {
    val max = DailyCap.MAX_DESTINATIONS_PER_DAY
    Column(horizontalAlignment = Alignment.End) {
        Text("$used of $max routes today", color = LavenderGrey, style = MaterialTheme.typography.labelSmall)
        Spacer(Modifier.height(4.dp))
        LinearProgressIndicator(
            progress = { used.toFloat() / max },
            color = Blush,
            trackColor = BlushSoft,
            strokeCap = StrokeCap.Round,
            modifier = Modifier.width(90.dp).height(6.dp),
        )
    }
}

private fun turnIcon(turn: Int): Int = when (turn) {
    NavPacket.TURN_LEFT -> R.drawable.ic_turn_left
    NavPacket.TURN_RIGHT -> R.drawable.ic_turn_right
    NavPacket.TURN_SLIGHT_LEFT -> R.drawable.ic_turn_slight_left
    NavPacket.TURN_SLIGHT_RIGHT -> R.drawable.ic_turn_slight_right
    NavPacket.TURN_SHARP_LEFT -> R.drawable.ic_turn_sharp_left
    NavPacket.TURN_SHARP_RIGHT -> R.drawable.ic_turn_sharp_right
    NavPacket.TURN_UTURN -> R.drawable.ic_u_turn_left
    NavPacket.TURN_ROUNDABOUT -> R.drawable.ic_roundabout_right
    NavPacket.TURN_ARRIVE -> R.drawable.ic_sports_score
    NavPacket.TURN_FORK_LEFT -> R.drawable.ic_fork_left
    NavPacket.TURN_FORK_RIGHT -> R.drawable.ic_fork_right
    NavPacket.TURN_MERGE -> R.drawable.ic_merge
    NavPacket.TURN_RAMP_LEFT -> R.drawable.ic_ramp_left
    NavPacket.TURN_RAMP_RIGHT -> R.drawable.ic_ramp_right
    NavPacket.TURN_NONE -> R.drawable.ic_directions_bike
    else -> R.drawable.ic_straight
}

// Android's built-in geocoder, not a billed Google Maps API
private suspend fun geocode(context: Context, address: String): Place? = withContext(Dispatchers.IO) {
    if (!Geocoder.isPresent()) return@withContext null
    try {
        @Suppress("DEPRECATION")
        val result = Geocoder(context).getFromLocationName(address, 1)?.firstOrNull() ?: return@withContext null
        Place(result.latitude, result.longitude, result.getAddressLine(0) ?: address)
    } catch (e: Exception) {
        null
    }
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

// design preview in Android Studio (Split/Design view), no phone, BLE, or Google calls needed
@androidx.compose.ui.tooling.preview.Preview(showBackground = true, backgroundColor = 0xFFF5F6FB, widthDp = 390)
@Composable
private fun HomePiecesPreview() {
    com.bikehud.app.ui.theme.BikeHUDTheme {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Header(HudBle.State.CONNECTED, "Riding to 1101 Beal Ave", {}, {}, {})
            TurnCard(HudCue(NavPacket.TURN_LEFT, 74, "toward Beal Ave", 3200), NavSession.Phase.NAVIGATING)
            TurnCard(HudCue.NONE, NavSession.Phase.READY)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Toggle("Simulate", R.drawable.ic_science, true) {}
                Toggle("Voice", R.drawable.ic_volume_off, false) {}
                Spacer(Modifier.weight(1f))
                RidesToday(used = 3)
            }
        }
    }
}
