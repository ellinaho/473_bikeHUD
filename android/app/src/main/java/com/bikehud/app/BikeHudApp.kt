package com.bikehud.app

import android.app.Application
import com.bikehud.app.ble.HudBle

// holds the BLE link so the nav update service and the UI share one connection
class BikeHudApp : Application() {
    lateinit var ble: HudBle
        private set

    override fun onCreate() {
        super.onCreate()
        ble = HudBle(this)
    }
}
