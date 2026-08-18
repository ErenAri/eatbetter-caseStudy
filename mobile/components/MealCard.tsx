import { Pressable, StyleSheet, Text, View } from "react-native";
import { Meal } from "../types/api";
import { colors, radius, spacing } from "../theme/tokens";

function summary(meal: Meal): string {
  const names = meal.items.filter((item) => !item.is_removed).slice(0, 3).map((item) => item.canonical?.name ?? item.observed_name);
  return names.length ? names.join(", ") : "Meal photo";
}
export function MealCard({ meal, onPress }: { meal: Meal; onPress: () => void }) {
  const reviewing = meal.status === "NEEDS_REVIEW";
  const incomplete = meal.status !== "CONFIRMED" && !reviewing;
  const activeIds = new Set(meal.items.filter((item) => !item.is_removed).map((item) => item.id));
  const remaining = meal.clarifications.filter((value) => value.status === "PENDING" && value.blocking && !value.resolution_satisfied && (value.meal_item_id === null || activeIds.has(value.meal_item_id))).length;
  const stateLabel = reviewing ? "Needs review" : incomplete ? "Incomplete" : `${Math.round(meal.totals.calories_kcal)} calories`;
  return <Pressable accessibilityRole="button" accessibilityLabel={`${summary(meal)}. ${stateLabel}`} onPress={onPress} style={styles.card}>
    <View style={styles.top}><Text style={styles.time}>{new Date(meal.logged_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</Text>{reviewing || incomplete ? <Text style={styles.pending}>{reviewing ? "Needs review" : "Incomplete"}</Text> : null}</View>
    <Text numberOfLines={2} style={styles.title}>{summary(meal)}</Text>
    {reviewing ? <Text style={styles.meta}>{remaining} {remaining === 1 ? "quick check" : "quick checks"} remaining · Continue</Text> : incomplete ? <Text style={styles.meta}>{meal.image_attached ? "Analysis can be resumed" : "Photo still needed"} · Continue</Text> : <Text style={styles.meta}>{Math.round(meal.totals.calories_kcal)} kcal · {Math.round(meal.totals.protein_g)}g protein · {Math.round(meal.totals.carbs_g)}g carbs</Text>}
  </Pressable>;
}
const styles = StyleSheet.create({ card: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, gap: spacing.xs, minHeight: 104 }, top: { flexDirection: "row", justifyContent: "space-between" }, time: { color: colors.textMuted, fontSize: 13 }, pending: { color: colors.attention, fontWeight: "800", fontSize: 12 }, title: { color: colors.text, fontSize: 17, fontWeight: "800" }, meta: { color: colors.textMuted, lineHeight: 19 } });
