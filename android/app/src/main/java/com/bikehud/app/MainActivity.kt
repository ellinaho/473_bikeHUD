package com.bikehud.app

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.bikehud.app.ble.HudBle
import com.bikehud.app.ble.NavPacket
import com.bikehud.app.ui.theme.BikeHUDTheme

class MainActivity : ComponentActivity() {
    private lateinit var ble: HudBle

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ble = HudBle(this)
        enableEdgeToEdge()
        setContent {
            BikeHUDTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    BleTestScreen(ble, Modifier.padding(innerPadding))
                }
            }
        }
    }

    override fun onDestroy() {
        // TODO: move BLE into the foreground service so it survives the activity
        ble.disconnect()
        super.onDestroy()
    }
}

private val blePermissions =
    if (Build.VERSION.SDK_INT >= 31) {
        arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
    } else {
        arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
    }

// temporary screen for testing the BLE link to the Pi, no Google API calls
@Composable
fun BleTestScreen(ble: HudBle, modifier: Modifier = Modifier) {
    val state by ble.state.collectAsState()
    var lastSend by remember { mutableStateOf("") }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        if (results.values.all { it }) ble.connect() else lastSend = "Bluetooth permission denied"
    }

    Column(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Helmet: $state")
        Text("Saved helmet: ${ble.savedAddress ?: "none"}")

        Button(onClick = {
            permissionLauncher.launch(blePermissions)
        }) { Text("Connect") }

        OutlinedButton(onClick = { ble.disconnect() }) { Text("Disconnect") }
        OutlinedButton(onClick = { ble.forget() }) { Text("Forget helmet") }

        Button(
            enabled = state == HudBle.State.CONNECTED,
            onClick = {
                val ok = ble.send(NavPacket.TURN_LEFT, 150, "State St", 1200)
                lastSend = if (ok) "Sent: left in 150 m onto State St" else "Send failed"
            }
        ) { Text("Send test packet") }

        if (lastSend.isNotEmpty()) Text(lastSend)
    }
}
