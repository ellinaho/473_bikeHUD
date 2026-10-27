package com.bikehud.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

// light and friendly, no dynamic colors so the app looks the same on every phone
private val BikeHudColors = lightColorScheme(
    primary = Apricot,
    onPrimary = CardWhite,
    secondary = DuskBlue,
    onSecondary = CardWhite,
    tertiary = Mint,
    background = Cloud,
    onBackground = InkBlack,
    surface = CardWhite,
    onSurface = InkBlack,
    surfaceVariant = Mist,
    onSurfaceVariant = LavenderGrey,
    outline = AlabasterGrey,
    error = Coral,
)

@Composable
fun BikeHUDTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = BikeHudColors,
        typography = Typography,
        content = content
    )
}
