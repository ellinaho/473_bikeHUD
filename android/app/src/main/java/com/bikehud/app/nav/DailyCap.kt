package com.bikehud.app.nav

import android.content.Context
import java.time.LocalDate

/**
 * Cost guard: limits how many destinations (billed Navigation SDK requests) can be set per day.
 * Count resets at midnight local time.
 */
class DailyCap(context: Context, private val maxPerDay: Int = MAX_DESTINATIONS_PER_DAY) {
    private val prefs = context.getSharedPreferences("daily_cap", Context.MODE_PRIVATE)

    val usedToday: Int
        get() = if (prefs.getString(KEY_DATE, null) == today()) prefs.getInt(KEY_COUNT, 0) else 0

    val remaining: Int get() = (maxPerDay - usedToday).coerceAtLeast(0)

    // call right before the billed request, returns false if over the cap
    fun tryUse(): Boolean {
        val used = usedToday
        if (used >= maxPerDay) return false
        prefs.edit().putString(KEY_DATE, today()).putInt(KEY_COUNT, used + 1).apply()
        return true
    }

    private fun today() = LocalDate.now().toString()

    companion object {
        const val MAX_DESTINATIONS_PER_DAY = 30
        private const val KEY_DATE = "date"
        private const val KEY_COUNT = "count"
    }
}
