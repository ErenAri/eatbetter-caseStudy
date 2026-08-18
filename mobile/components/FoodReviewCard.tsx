import { Pressable, StyleSheet, Text, View } from "react-native";
import { MealItem } from "../types/api";
import { colors, radius, spacing } from "../theme/tokens";

export function FoodReviewCard({ item, busy, onEditAmount, onEditFood, onRemove }: { item: MealItem; busy: boolean; onEditAmount: () => void; onEditFood: () => void; onRemove: () => void }) {
  if (item.is_removed) return null;
  const name = item.canonical?.name ?? item.observed_name;
  const ready = item.review_status === "READY";
  return <View accessibilityLabel={`${name}. ${ready ? "Looks good" : "Needs attention"}`} style={styles.card}>
    <Text style={styles.name}>{name}</Text>
    {item.preparation_method ? <Text style={styles.preparation}>{item.preparation_method}</Text> : null}
    {item.portion.confirmed_g !== null ? <Text style={styles.portion}>About {Math.round(item.portion.confirmed_g)} g</Text> : <Text style={styles.pending}>Amount needs a quick check</Text>}
    {item.nutrition ? <Text style={styles.nutrition}>{Math.round(item.nutrition.calories_kcal)} kcal</Text> : <Text style={styles.note}>Calories calculated after amount is confirmed</Text>}
    <Text style={[styles.state, !ready && styles.pending]}>{ready ? "✓ Looks good" : item.review_status === "NEEDS_IDENTITY" ? "Food needs a quick check" : "Review needed"}</Text>
    <View style={styles.actions}>
      <Pressable accessibilityRole="button" disabled={busy} onPress={onEditAmount}><Text style={styles.action}>Change amount</Text></Pressable>
      {item.candidates.length ? <Pressable accessibilityRole="button" disabled={busy} onPress={onEditFood}><Text style={styles.action}>Change food</Text></Pressable> : null}
      <Pressable accessibilityRole="button" disabled={busy} onPress={onRemove}><Text style={styles.remove}>Remove</Text></Pressable>
    </View>
  </View>;
}
const styles = StyleSheet.create({ card: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, gap: spacing.xs }, name: { color: colors.text, fontSize: 18, fontWeight: "900" }, preparation: { color: colors.textMuted, textTransform: "capitalize" }, portion: { color: colors.text, marginTop: spacing.xs }, nutrition: { color: colors.text, fontWeight: "800", fontSize: 17 }, note: { color: colors.textMuted, fontSize: 13 }, state: { color: colors.primary, fontWeight: "800", marginTop: spacing.xs }, pending: { color: colors.attention, fontWeight: "700" }, actions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginTop: spacing.sm }, action: { color: colors.primary, fontWeight: "700", minHeight: 34 }, remove: { color: colors.danger, fontWeight: "700", minHeight: 34 } });
