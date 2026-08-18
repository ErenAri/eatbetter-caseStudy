import { FlatList, StyleSheet, Text, View } from "react-native";
import { EmptyState, ErrorState, LoadingState, Screen, Button } from "../../components/Primitives";
import { MealCard } from "../../components/MealCard";
import { NutritionSummary } from "../../components/NutritionSummary";
import { colors, spacing } from "../../theme/tokens";
import { Meal, NutritionTotals } from "../../types/api";
import { BackendHealth } from "../../types/health";

export function TodayScreen({ meals, totals, loading, error = null, health = { status: "loading", label: "Connecting" }, onRetry = () => undefined, onLog, onOpen }: { meals: Meal[]; totals: NutritionTotals; loading: boolean; error?: string | null; health?: BackendHealth; onRetry?: () => void; onLog: () => void; onOpen: (meal: Meal) => void }) {
  const date = new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
  return <Screen>
    <View style={styles.header}><View><Text style={styles.title}>Today</Text><Text style={styles.date}>{date}</Text></View>{__DEV__ ? <Text style={styles.dev}>{health.label}</Text> : null}</View>
    {loading ? <LoadingState message="Loading today's meals…" /> : error ? <ErrorState message={error} action={<Button label="Try again" onPress={onRetry} secondary />} /> : <>
      <View style={styles.summary}><Text style={styles.todayLabel}>Eaten today</Text><NutritionSummary totals={totals} /></View>
      <Text style={styles.heading}>Meals</Text>
      <FlatList data={meals} keyExtractor={(meal) => meal.id} contentContainerStyle={styles.list} ListEmptyComponent={<EmptyState title="No meals logged yet" body="Take a photo of your meal and we'll help identify the foods and portions." action={<Button label="Log your first meal" onPress={onLog} />} />} renderItem={({ item }) => <MealCard meal={item} onPress={() => onOpen(item)} />} />
    </>}
    {!loading && !error && meals.length ? <Button label="＋  Log meal" onPress={onLog} /> : null}
  </Screen>;
}
const styles = StyleSheet.create({ header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: spacing.lg }, title: { color: colors.text, fontSize: 36, fontWeight: "900" }, date: { color: colors.textMuted, marginTop: 2 }, dev: { color: colors.textMuted, fontSize: 11, borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingHorizontal: 8, paddingVertical: 4 }, summary: { gap: spacing.sm, marginBottom: spacing.lg }, todayLabel: { color: colors.textMuted, fontWeight: "700" }, heading: { color: colors.text, fontSize: 20, fontWeight: "900" }, list: { flexGrow: 1, gap: spacing.sm, paddingVertical: spacing.md } });
