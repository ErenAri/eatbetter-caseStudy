import { StyleSheet, Text, View } from "react-native";
import { NutritionTotals } from "../types/api";
import { colors, spacing } from "../theme/tokens";

export function NutritionSummary({ totals, compact = false }: { totals: NutritionTotals; compact?: boolean }) {
  return <View accessibilityLabel={`${Math.round(totals.calories_kcal)} calories`} style={styles.wrap}>
    <Text style={[styles.calories, compact && styles.compact]}>{Math.round(totals.calories_kcal)} kcal</Text>
    <View style={styles.macros}>
      <Text style={styles.macro}>Protein  {Math.round(totals.protein_g)} g</Text>
      <Text style={styles.macro}>Carbs  {Math.round(totals.carbs_g)} g</Text>
      <Text style={styles.macro}>Fat  {Math.round(totals.fat_g)} g</Text>
    </View>
  </View>;
}
const styles = StyleSheet.create({ wrap: { gap: spacing.sm }, calories: { color: colors.text, fontSize: 38, fontWeight: "900" }, compact: { fontSize: 20 }, macros: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md }, macro: { color: colors.textMuted, fontSize: 14 } });
