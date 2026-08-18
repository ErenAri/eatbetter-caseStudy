import { Alert, StyleSheet, Text, View } from "react-native";
import { NutritionSummary } from "../../components/NutritionSummary";
import { Button, ErrorState, Pill, Screen } from "../../components/Primitives";
import { colors, radius, spacing } from "../../theme/tokens";
import { Meal } from "../../types/api";

export function MealDetailScreen({ meal, busy, error, onResume, onDiscard, onBack }: { meal: Meal; busy: boolean; error: string | null; onResume?: () => void; onDiscard?: () => void; onBack: () => void }) {
  const adjustments = meal.corrections.length;
  const confirmed = meal.status === "CONFIRMED";
  const sources = new Set(meal.items.filter((item) => !item.is_removed).map((item) => item.canonical?.source).filter(Boolean));
  const nutritionSource = sources.size === 1 && sources.has("TEST_DEMO_DATA") ? "Test/demo nutrition data" : sources.size === 1 && sources.has("USDA_FDC") ? "Nutrition data: USDA FoodData Central" : "Nutrition data: verified sources";
  const statusText = meal.status === "UPLOADED" ? (meal.image_attached ? "Photo uploaded; analysis not finished." : "This attempt still needs a photo.") : meal.status === "ANALYZING" ? "Analysis was interrupted and can be resumed." : meal.status === "FAILED_RETRYABLE" ? "Analysis failed temporarily and can be retried." : meal.status === "FAILED_PERMANENT" ? "This photo could not be analyzed." : "This meal still needs review.";
  const confirmDiscard = () => Alert.alert(
    "Discard this meal?",
    "This permanently deletes the incomplete meal and its uploaded photo.",
    [
      { text: "Keep meal", style: "cancel" },
      { text: "Discard", style: "destructive", onPress: onDiscard },
    ],
  );
  return <Screen scroll>
    <Text accessibilityRole="button" onPress={onBack} style={styles.back}>‹ Today</Text>
    <Text style={styles.title}>{confirmed ? "Meal saved" : "Incomplete meal"}</Text>
    <Text style={styles.time}>{new Date(meal.logged_at).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}</Text>
    <Pill>{confirmed ? "Saved" : meal.status === "FAILED_PERMANENT" ? "Could not analyze" : "Not saved"}</Pill>
    {!confirmed ? <Text style={styles.notice}>{statusText}</Text> : null}
    {confirmed ? <View style={styles.summary}><NutritionSummary totals={meal.totals} /></View> : null}
    <Text style={styles.heading}>Foods</Text>
    {meal.items.filter((item) => !item.is_removed).map((item) => <View accessibilityLabel={item.canonical?.name ?? item.observed_name} key={item.id} style={styles.item}><Text style={styles.food}>{item.canonical?.name ?? item.observed_name}</Text><Text style={styles.meta}>{item.portion.confirmed_g === null ? "Amount not confirmed" : `${Math.round(item.portion.confirmed_g)} g`}{item.nutrition ? ` · ${Math.round(item.nutrition.calories_kcal)} kcal` : ""}</Text>{item.is_user_added ? <Text style={styles.adjusted}>Added by you</Text> : null}</View>)}
    {adjustments ? <Text style={styles.adjustments}>{adjustments} {adjustments === 1 ? "adjustment" : "adjustments"} made</Text> : null}
    {error ? <ErrorState message={error} /> : null}
    {!confirmed && onResume ? <Button label={busy ? "Resuming…" : "Resume analysis"} disabled={busy} onPress={onResume} /> : null}
    {!confirmed && onDiscard ? <Button label="Discard and start over" disabled={busy} onPress={confirmDiscard} destructive /> : null}
    {confirmed ? <><Text style={styles.source}>{nutritionSource}</Text>{meal.image_attached ? <Text style={styles.photoNote}>Analyzed from your photo</Text> : null}</> : null}
  </Screen>;
}
const styles = StyleSheet.create({ back: { color: colors.primary, fontWeight: "800", minHeight: 36 }, title: { color: colors.text, fontSize: 33, fontWeight: "900" }, time: { color: colors.textMuted, marginVertical: spacing.xs }, notice: { color: colors.textMuted, lineHeight: 21, marginVertical: spacing.md }, summary: { paddingVertical: spacing.lg }, heading: { color: colors.text, fontSize: 20, fontWeight: "900", marginBottom: spacing.sm }, item: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm }, food: { color: colors.text, fontSize: 17, fontWeight: "800" }, meta: { color: colors.textMuted, marginTop: spacing.xs }, adjusted: { color: colors.primary, fontSize: 12, fontWeight: "700", marginTop: spacing.xs }, adjustments: { color: colors.primary, fontWeight: "700", marginTop: spacing.md }, source: { color: colors.textMuted, fontSize: 12, marginTop: spacing.xl }, photoNote: { color: colors.textMuted, fontSize: 12, marginTop: spacing.xs } });
