import { StyleSheet, Text, View } from "react-native";
import { NutritionSummary } from "../../components/NutritionSummary";
import { Pill, Screen } from "../../components/Primitives";
import { colors, radius, spacing } from "../../theme/tokens";
import { Meal } from "../../types/api";

export function MealDetailScreen({ meal, onBack }: { meal: Meal; onBack: () => void }) {
  const adjustments = meal.corrections.length;
  return <Screen scroll>
    <Text accessibilityRole="button" onPress={onBack} style={styles.back}>‹ Today</Text>
    <Text style={styles.title}>Meal saved</Text>
    <Text style={styles.time}>{new Date(meal.logged_at).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}</Text>
    <Pill>{meal.status === "CONFIRMED" ? "Saved" : "Review pending"}</Pill>
    <View style={styles.summary}><NutritionSummary totals={meal.totals} /></View>
    <Text style={styles.heading}>Foods</Text>
    {meal.items.filter((item) => !item.is_removed).map((item) => <View accessibilityLabel={item.canonical?.name ?? item.observed_name} key={item.id} style={styles.item}><Text style={styles.food}>{item.canonical?.name ?? item.observed_name}</Text><Text style={styles.meta}>{item.portion.confirmed_g === null ? "Amount not confirmed" : `${Math.round(item.portion.confirmed_g)} g`}{item.nutrition ? ` · ${Math.round(item.nutrition.calories_kcal)} kcal` : ""}</Text>{item.is_user_added ? <Text style={styles.adjusted}>Added by you</Text> : null}</View>)}
    {adjustments ? <Text style={styles.adjustments}>{adjustments} {adjustments === 1 ? "adjustment" : "adjustments"} made</Text> : null}
    <Text style={styles.source}>Nutrition data: USDA FoodData Central</Text>
    <Text style={styles.photoNote}>Analyzed from your photo</Text>
  </Screen>;
}
const styles = StyleSheet.create({ back: { color: colors.primary, fontWeight: "800", minHeight: 36 }, title: { color: colors.text, fontSize: 33, fontWeight: "900" }, time: { color: colors.textMuted, marginVertical: spacing.xs }, summary: { paddingVertical: spacing.lg }, heading: { color: colors.text, fontSize: 20, fontWeight: "900", marginBottom: spacing.sm }, item: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm }, food: { color: colors.text, fontSize: 17, fontWeight: "800" }, meta: { color: colors.textMuted, marginTop: spacing.xs }, adjusted: { color: colors.primary, fontSize: 12, fontWeight: "700", marginTop: spacing.xs }, adjustments: { color: colors.primary, fontWeight: "700", marginTop: spacing.md }, source: { color: colors.textMuted, fontSize: 12, marginTop: spacing.xl }, photoNote: { color: colors.textMuted, fontSize: 12, marginTop: spacing.xs } });
