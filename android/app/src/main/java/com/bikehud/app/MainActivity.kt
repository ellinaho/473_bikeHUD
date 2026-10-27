package com.bikehud.app

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.ui.Modifier
import com.bikehud.app.nav.NavSession
import com.bikehud.app.ui.HomeScreen
import com.bikehud.app.ui.theme.BikeHUDTheme

class MainActivity : ComponentActivity() {
    private lateinit var nav: NavSession

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        nav = NavSession(this)
        val ble = (application as BikeHudApp).ble
        // dark status bar icons on the light background
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
        )
        setContent {
            BikeHUDTheme {
                Scaffold(
                    modifier = Modifier.fillMaxSize(),
                    containerColor = MaterialTheme.colorScheme.background,
                ) { innerPadding ->
                    HomeScreen(ble, nav, lifecycle, Modifier.padding(innerPadding))
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
