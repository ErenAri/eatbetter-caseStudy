import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { ClarificationCard } from "../../components/ClarificationCard";
import { FoodReviewCard } from "../../components/FoodReviewCard";
import { Button, ErrorState, Screen } from "../../components/Primitives";
import { colors, radius, spacing } from "../../theme/tokens";
import { Meal, MealItem } from "../../types/api";

type Update = { candidate_rank?: number; portion_g?: number; preparation_method?: string | null };
export function ReviewScreen({ meal, busyKey, error, onAnswer, onUpdate, onRemove, onAdd, onReplace, onConfirm, onBack }: {
  meal: Meal;
  busyKey: string | null;
  error: string | null;
  onAnswer: (clarificationId: string, answer: { option_id: string } | { custom_grams: number }) => void;
  onUpdate: (item: MealItem, update: Update) => Promise<boolean>;
  onRemove: (item: MealItem) => void;
  onAdd: (query: string, grams: number) => Promise<boolean>;
  onReplace: (item: MealItem, query: string, grams: number) => Promise<boolean>;
  onConfirm: () => void;
  onBack: () => void;
}) {
  const activeItems = meal.items.filter((item) => !item.is_removed);
  const activeIds = new Set(activeItems.map((item) => item.id));
  const blockers = meal.clarifications.filter((value) => value.status === "PENDING" && value.blocking && !value.resolution_satisfied && (value.meal_item_id === null || activeIds.has(value.meal_item_id)));
  const current = blockers[0];
  const canSave = blockers.length === 0 && activeItems.every((item) => item.review_status === "READY" && item.nutrition !== null);
  const [editor, setEditor] = useState<{ item: MealItem; kind: "amount" | "food" } | null>(null);
  const [amount, setAmount] = useState("");
  const [adding, setAdding] = useState<{ replacing: MealItem | null } | null>(null);
  const [query, setQuery] = useState("");
  const [addGrams, setAddGrams] = useState("");
  useEffect(() => { if (current) setEditor(null); }, [current?.id]);

  const openAmount = (item: MealItem) => { setAmount(item.portion.confirmed_g === null ? "" : String(Math.round(item.portion.confirmed_g))); setEditor({ item, kind: "amount" }); };
  return <Screen>
    <Text accessibilityRole="button" onPress={onBack} style={styles.back}>‹ Today</Text>
    <View style={styles.header}><View><Text style={styles.title}>Review meal</Text><Text style={styles.subtitle}>{activeItems.length} {activeItems.length === 1 ? "food" : "foods"} found</Text></View><Text style={styles.count}>{blockers.length ? `${blockers.length} quick ${blockers.length === 1 ? "check" : "checks"}` : "Ready to save"}</Text></View>
    <ScrollView contentContainerStyle={styles.scroll}>
      {current ? <ClarificationCard clarification={current} busy={busyKey === current.id} onAnswer={(answer) => onAnswer(current.id, answer)} onManualSearch={() => { const replacing = meal.items.find((item) => item.id === current.meal_item_id) ?? null; setAdding({ replacing }); setQuery(replacing?.observed_name ?? ""); setAddGrams(replacing?.portion.confirmed_g === null || replacing?.portion.confirmed_g === undefined ? "" : String(Math.round(replacing.portion.confirmed_g))); }} /> : null}
      <Text style={styles.section}>Foods</Text>
      {activeItems.map((item) => <FoodReviewCard key={item.id} item={item} busy={busyKey === item.id} onEditAmount={() => openAmount(item)} onEditFood={() => setEditor({ item, kind: "food" })} onRemove={() => onRemove(item)} />)}
      {editor ? <View style={styles.editor}><Text style={styles.editorTitle}>{editor.kind === "amount" ? `Change amount for ${editor.item.canonical?.name ?? editor.item.observed_name}` : "Choose a different food"}</Text>
        {editor.kind === "amount" ? <><TextInput accessibilityLabel="Amount in grams" value={amount} onChangeText={setAmount} keyboardType="decimal-pad" placeholder="Grams" style={styles.input} /><Button label="Save amount" disabled={busyKey === editor.item.id || amount.trim() === "" || !Number.isFinite(Number(amount)) || Number(amount) <= 0} onPress={() => { void onUpdate(editor.item, { portion_g: Number(amount) }).then((saved) => { if (saved) { setEditor(null); setAmount(""); } }); }} /></> : editor.item.candidates.map((candidate) => <Pressable accessibilityRole="button" accessibilityLabel={candidate.display_name} key={candidate.rank} onPress={() => { void onUpdate(editor.item, { candidate_rank: candidate.rank }).then((saved) => { if (saved) setEditor(null); }); }} style={styles.choice}><Text style={styles.choiceText}>{candidate.display_name}</Text></Pressable>)}
        <Button label="Cancel" onPress={() => setEditor(null)} secondary />
      </View> : null}
      {adding ? <View style={styles.editor}><Text style={styles.editorTitle}>{adding.replacing ? `Replace ${adding.replacing.observed_name}` : "Add a missing food"}</Text><Text style={styles.help}>{adding.replacing ? "Search for the correct food. This replaces the original item and resolves its old question." : "Search by food name and enter the amount you had. Nutrition is matched by the server."}</Text><TextInput accessibilityLabel="Food search" value={query} onChangeText={setQuery} placeholder="e.g. olive oil" style={styles.input} /><TextInput accessibilityLabel="Food amount in grams" value={addGrams} onChangeText={setAddGrams} keyboardType="decimal-pad" placeholder="Amount in grams" style={styles.input} /><Button label={adding.replacing ? "Replace food" : "Add food"} disabled={!query.trim() || !addGrams.trim() || !Number.isFinite(Number(addGrams)) || Number(addGrams) <= 0 || busyKey === "add" || busyKey === adding.replacing?.id} onPress={() => { const operation = adding.replacing ? onReplace(adding.replacing, query.trim(), Number(addGrams)) : onAdd(query.trim(), Number(addGrams)); void operation.then((saved) => { if (saved) { setAdding(null); setQuery(""); setAddGrams(""); } }); }} /><Button label="Cancel" onPress={() => setAdding(null)} secondary /></View> : <Button label="＋ Add food" onPress={() => { setAdding({ replacing: null }); setQuery(""); setAddGrams(""); }} secondary />}
      {error ? <ErrorState message={error} /> : null}
      <View style={styles.save}><Button label={busyKey === "confirm" ? "Saving…" : canSave ? "Save meal" : `Review ${blockers.length || 1} ${blockers.length === 1 ? "item" : "items"} to continue`} disabled={!canSave || busyKey !== null} onPress={onConfirm} /></View>
    </ScrollView>
  </Screen>;
}

const styles = StyleSheet.create({ back: { color: colors.primary, fontWeight: "800", minHeight: 34 }, header: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md, alignItems: "flex-end" }, title: { color: colors.text, fontSize: 31, fontWeight: "900" }, subtitle: { color: colors.textMuted, marginTop: 3 }, count: { color: colors.attention, fontWeight: "800", maxWidth: 110, textAlign: "right" }, scroll: { paddingVertical: spacing.lg, paddingBottom: 60, gap: spacing.md }, section: { color: colors.text, fontSize: 20, fontWeight: "900", marginTop: spacing.xs }, editor: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, gap: spacing.sm }, editorTitle: { color: colors.text, fontSize: 18, fontWeight: "900" }, help: { color: colors.textMuted, lineHeight: 20 }, input: { minHeight: 52, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.md, color: colors.text }, choice: { minHeight: 52, justifyContent: "center", paddingHorizontal: spacing.md, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md }, choiceText: { color: colors.text, fontWeight: "700" }, save: { marginTop: spacing.sm } });
