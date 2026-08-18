import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Clarification } from "../types/api";
import { colors, radius, spacing } from "../theme/tokens";
import { Button } from "./Primitives";

type Props = {
  clarification: Clarification;
  busy: boolean;
  onAnswer: (answer: { option_id: string } | { custom_grams: number }) => void;
  onManualSearch: () => void;
};

export function ClarificationCard({ clarification, busy, onAnswer, onManualSearch }: Props) {
  const [custom, setCustom] = useState("");
  const [manual, setManual] = useState(false);
  const intro = clarification.type === "HIDDEN_INGREDIENT" ? "One quick check" : clarification.type === "CANONICAL_SELECTION" || clarification.type === "FOOD_IDENTITY" ? "Choose food" : "Choose amount";
  const helper = clarification.type === "HIDDEN_INGREDIENT" ? "Ingredients like oil can significantly change the meal estimate." : null;
  return <View accessibilityLabel={`${intro}. ${clarification.question}`} style={styles.card}>
    <Text style={styles.eyebrow}>{intro}</Text>
    <Text style={styles.question}>{clarification.question}</Text>
    {helper ? <Text style={styles.helper}>{helper}</Text> : null}
    <View style={styles.options}>
      {clarification.options.map((option) => {
        const isManual = "action" in option.value && option.value.action === "MANUAL_SEARCH";
        const grams = "grams" in option.value ? option.value.grams : null;
        return <Pressable key={option.id} accessibilityRole="button" accessibilityLabel={option.label} disabled={busy} onPress={() => isManual ? onManualSearch() : onAnswer({ option_id: option.id })} style={({ pressed }) => [styles.option, pressed && styles.pressed]}><Text style={styles.optionText}>{option.label}</Text>{grams !== null ? <Text style={styles.optionDetail}>About {Number(grams).toLocaleString()} g</Text> : null}</Pressable>;
      })}
    </View>
    {clarification.type === "CANONICAL_SELECTION" ? <Pressable accessibilityRole="button" onPress={onManualSearch}><Text style={styles.manualLink}>None of these</Text></Pressable> : null}
    {clarification.type === "PORTION" ? <>
      <Pressable accessibilityRole="button" onPress={() => setManual((value) => !value)}><Text style={styles.manualLink}>Enter amount manually</Text></Pressable>
      {manual ? <View style={styles.manualRow}><TextInput accessibilityLabel="Custom amount in grams" keyboardType="decimal-pad" value={custom} onChangeText={setCustom} placeholder="Grams" style={styles.input} /><View style={styles.flex}><Button label="Use amount" disabled={busy || !Number.isFinite(Number(custom)) || Number(custom) < 0 || custom.trim() === ""} onPress={() => onAnswer({ custom_grams: Number(custom) })} /></View></View> : null}
    </> : null}
  </View>;
}

const styles = StyleSheet.create({ card: { backgroundColor: colors.attentionSoft, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.sm, borderWidth: 1, borderColor: "#EBCB9F" }, eyebrow: { color: colors.attention, fontSize: 12, fontWeight: "900", textTransform: "uppercase", letterSpacing: 1 }, question: { color: colors.text, fontSize: 22, lineHeight: 28, fontWeight: "900" }, helper: { color: colors.textMuted, lineHeight: 20 }, options: { gap: spacing.sm, marginTop: spacing.xs }, option: { minHeight: 52, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, justifyContent: "center", paddingHorizontal: spacing.md }, pressed: { borderColor: colors.primary }, optionText: { color: colors.text, fontWeight: "800" }, optionDetail: { color: colors.textMuted, marginTop: 2, fontSize: 13 }, manualLink: { color: colors.primary, fontWeight: "800", paddingVertical: spacing.sm }, manualRow: { flexDirection: "row", gap: spacing.sm, alignItems: "center" }, input: { width: 100, minHeight: 52, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.md, color: colors.text }, flex: { flex: 1 } });
