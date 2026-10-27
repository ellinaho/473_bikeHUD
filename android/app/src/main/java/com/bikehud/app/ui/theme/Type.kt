package com.bikehud.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import com.bikehud.app.R

// Nunito (rounded, friendly), one variable font file for every weight. License: android/app/NUNITO_OFL.txt
@OptIn(ExperimentalTextApi::class)
private fun nunito(weight: Int) = Font(
    R.font.nunito,
    weight = FontWeight(weight),
    variationSettings = FontVariation.Settings(FontVariation.weight(weight)),
)

val Nunito = FontFamily(nunito(400), nunito(600), nunito(700), nunito(800), nunito(900))

private val base = Typography()

// every Material text style, just switched to Nunito
val Typography = Typography(
    displayLarge = base.displayLarge.copy(fontFamily = Nunito),
    displayMedium = base.displayMedium.copy(fontFamily = Nunito),
    displaySmall = base.displaySmall.copy(fontFamily = Nunito),
    headlineLarge = base.headlineLarge.copy(fontFamily = Nunito),
    headlineMedium = base.headlineMedium.copy(fontFamily = Nunito),
    headlineSmall = base.headlineSmall.copy(fontFamily = Nunito),
    titleLarge = base.titleLarge.copy(fontFamily = Nunito, fontWeight = FontWeight.Bold),
    titleMedium = base.titleMedium.copy(fontFamily = Nunito, fontWeight = FontWeight.Bold),
    titleSmall = base.titleSmall.copy(fontFamily = Nunito, fontWeight = FontWeight.Bold),
    bodyLarge = base.bodyLarge.copy(fontFamily = Nunito),
    bodyMedium = base.bodyMedium.copy(fontFamily = Nunito),
    bodySmall = base.bodySmall.copy(fontFamily = Nunito),
    labelLarge = base.labelLarge.copy(fontFamily = Nunito, fontWeight = FontWeight.Bold),
    labelMedium = base.labelMedium.copy(fontFamily = Nunito, fontWeight = FontWeight.Bold),
    labelSmall = base.labelSmall.copy(fontFamily = Nunito, fontWeight = FontWeight.SemiBold),
)
