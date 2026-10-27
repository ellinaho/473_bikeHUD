package com.bikehud.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * BLE link to the helmet Pi. Phone is the central, Pi is the peripheral (nav/nav_receiver.py).
 * - first connect scans for the nav service, then the Pi's address is saved and reused
 * - reconnects on its own if the helmet power cycles, until disconnect() is called
 * - callers must have BLUETOOTH_SCAN + BLUETOOTH_CONNECT (or location on Android 10/11) before connect()
 */
@SuppressLint("MissingPermission")
class HudBle(context: Context) {
    enum class State { DISCONNECTED, BLUETOOTH_OFF, SCANNING, NOT_FOUND, CONNECTING, CONNECTED }

    private val appContext = context.applicationContext
    private val adapter = appContext.getSystemService(BluetoothManager::class.java)?.adapter
    private val prefs = appContext.getSharedPreferences("hud_ble", Context.MODE_PRIVATE)
    private val handler = Handler(Looper.getMainLooper())

    private val _state = MutableStateFlow(State.DISCONNECTED)
    val state: StateFlow<State> = _state

    @Volatile private var gatt: BluetoothGatt? = null
    @Volatile private var navChar: BluetoothGattCharacteristic? = null
    @Volatile private var mtu = DEFAULT_MTU
    @Volatile private var wantConnected = false
    private var scanning = false

    val savedAddress: String? get() = prefs.getString(KEY_ADDRESS, null)

    fun connect() {
        if (adapter == null || !adapter.isEnabled) {
            _state.value = State.BLUETOOTH_OFF
            return
        }
        wantConnected = true
        val saved = savedAddress
        if (saved != null) connectTo(adapter.getRemoteDevice(saved), autoConnect = false) else startScan()
    }

    fun disconnect() {
        wantConnected = false
        stopScan()
        closeGatt()
        _state.value = State.DISCONNECTED
    }

    // forget the saved Pi so the next connect() scans again
    fun forget() {
        disconnect()
        prefs.edit().remove(KEY_ADDRESS).apply()
    }

    /**
     * - sends one nav packet, write without response
     * - street name is shortened if the negotiated MTU is too small for the full packet
     * - returns false if not connected or the write was rejected
     */
    fun send(turn: Int, dist: Int, street: String, remaining: Int = 0): Boolean {
        val g = gatt ?: return false
        val c = navChar ?: return false
        val maxName = mtu - ATT_OVERHEAD - NavPacket.HEADER_SIZE
        val packet = NavPacket.pack(turn, dist, street, remaining, maxName)

        return if (Build.VERSION.SDK_INT >= 33) {
            g.writeCharacteristic(c, packet, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE) ==
                BluetoothStatusCodes.SUCCESS
        } else {
            c.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            @Suppress("DEPRECATION")
            c.value = packet
            @Suppress("DEPRECATION")
            g.writeCharacteristic(c)
        }
    }

    private fun startScan() {
        val scanner = adapter?.bluetoothLeScanner ?: return
        val filter = ScanFilter.Builder().setServiceUuid(ParcelUuid(NavPacket.SERVICE_UUID)).build()
        val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        scanning = true
        _state.value = State.SCANNING
        scanner.startScan(listOf(filter), settings, scanCallback)
        handler.postDelayed(scanTimeout, SCAN_TIMEOUT_MS)
    }

    private fun stopScan() {
        handler.removeCallbacks(scanTimeout)
        if (scanning) {
            scanning = false
            adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        }
    }

    private val scanTimeout = Runnable {
        stopScan()
        if (_state.value == State.SCANNING) _state.value = State.NOT_FOUND
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            if (!scanning) return
            stopScan()
            connectTo(result.device, autoConnect = false)
        }

        override fun onScanFailed(errorCode: Int) {
            Log.w(TAG, "scan failed $errorCode")
            stopScan()
            _state.value = State.NOT_FOUND
        }
    }

    // autoConnect = true waits in the background until the Pi shows up again (used for reconnects)
    private fun connectTo(device: BluetoothDevice, autoConnect: Boolean) {
        closeGatt()
        _state.value = State.CONNECTING
        gatt = device.connectGatt(appContext, autoConnect, gattCallback, BluetoothDevice.TRANSPORT_LE)
    }

    private fun closeGatt() {
        navChar = null
        mtu = DEFAULT_MTU
        gatt?.close()
        gatt = null
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                g.requestMtu(REQUESTED_MTU)
                return
            }
            if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                Log.i(TAG, "disconnected, status $status")
                val device = g.device
                closeGatt()
                if (wantConnected) {
                    handler.post { connectTo(device, autoConnect = true) }
                } else {
                    _state.value = State.DISCONNECTED
                }
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, newMtu: Int, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) mtu = newMtu
            g.discoverServices()
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            val c = g.getService(NavPacket.SERVICE_UUID)?.getCharacteristic(NavPacket.CHAR_UUID)
            if (status != BluetoothGatt.GATT_SUCCESS || c == null) {
                // not our helmet (or receiver not running), drop the saved address
                Log.w(TAG, "nav service not found on ${g.device.address}")
                prefs.edit().remove(KEY_ADDRESS).apply()
                handler.post { disconnect() }
                return
            }
            navChar = c
            prefs.edit().putString(KEY_ADDRESS, g.device.address).apply()
            _state.value = State.CONNECTED
        }
    }

    companion object {
        private const val TAG = "HudBle"
        private const val KEY_ADDRESS = "helmet_address"
        private const val SCAN_TIMEOUT_MS = 15_000L
        private const val DEFAULT_MTU = 23
        private const val REQUESTED_MTU = 64
        private const val ATT_OVERHEAD = 3
    }
}
