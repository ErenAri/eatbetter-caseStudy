import { Pressable, StyleSheet, Text, View } from "react-native";
import { Meal } from "../types/api";
import { colors, radius, spacing } from "../theme/tokens";

function summary(meal: Meal): string {
  const names = meal.items.filter((item) => !item.is_removed).slice(0, 3).map((item) => item.canonical?.name ?? item.observed_name);
  return names.length ? names.join(", ") : "Meal photo";
}
export function MealCard({ meal, onPress }: { meal: Meal; onPress: () => void }) {
  const pending = meal.status === "NEEDS_REVIEW";
  const remaining = meal.clarifications.filter((value) => value.blocking && !value.resolution_satisfied).length;
  return <Pressable accessibilityRole="button" accessibilityLabel={`${summary(meal)}. ${pending ? "Needs review" : `${Math.round(meal.totals.calories_kcal)} calories`}`} onPress={onPress} style={styles.card}>
    <View style={styles.top}><Text style={styles.time}>{new Date(meal.logged_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</Text>{pending ? <Text style={styles.pending}>Needs review</Text> : null}</View>
    <Text numberOfLines={2} style={styles.title}>{summary(meal)}</Text>
    {pending ? <Text style={styles.meta}>{remaining} {remaining === 1 ? "quick check" : "quick checks"} remaining · Continue</Text> : <Text style={styles.meta}>{Math.round(meal.totals.calories_kcal)} kcal · {Math.round(meal.totals.protein_g)}g protein · {Math.round(meal.totals.carbs_g)}g carbs</Text>}
  </Pressable>;
}
const styles = StyleSheet.create({ card: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, gap: spacing.xs, minHeight: 104 }, top: { flexDirection: "row", justifyContent: "space-between" }, time: { color: colors.textMuted, fontSize: 13 }, pending: { color: colors.attention, fontWeight: "800", fontSize: 12 }, title: { color: colors.text, fontSize: 17, fontWeight: "800" }, meta: { color: colors.textMuted, lineHeight: 19 } });
