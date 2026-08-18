import { PropsWithChildren, ReactNode } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { colors, radius, spacing } from "../theme/tokens";

export const palette = { ink: colors.text, muted: colors.textMuted, paper: colors.background, card: colors.surface, green: colors.primary, mint: colors.primarySoft, amber: colors.attention, line: colors.border };

export function Screen({ children, scroll = false }: PropsWithChildren<{ scroll?: boolean }>) {
  const content = scroll ? <ScrollView contentContainerStyle={styles.scroll}>{children}</ScrollView> : <View style={styles.content}>{children}</View>;
  return <View style={styles.safe}>{content}</View>;
}
export function Card({ children }: PropsWithChildren) { return <View style={styles.card}>{children}</View>; }
export function LoadingState({ message = "Loading…" }: { message?: string }) {
  return <View style={styles.stateRow}><ActivityIndicator color={colors.primary} /><Text accessibilityRole="progressbar" style={styles.stateText}>{message}</Text></View>;
}
export function ErrorState({ message, action }: { message: string; action?: ReactNode }) {
  return <View accessibilityRole="alert" style={styles.errorBox}><Text style={styles.errorText}>{message}</Text>{action}</View>;
}
export function EmptyState({ title, body, action }: { title: string; body: string; action: ReactNode }) {
  return <View style={styles.empty}><Text style={styles.emptyTitle}>{title}</Text><Text style={styles.stateText}>{body}</Text>{action}</View>;
}
export function Pill({ children, warning = false }: PropsWithChildren<{ warning?: boolean }>) {
  return <Text style={[styles.pill, warning && styles.warning]}>{children}</Text>;
}
export function Button({ label, onPress, secondary = false, destructive = false, disabled = false, accessibilityLabel }: { label: string; onPress: () => void; secondary?: boolean; destructive?: boolean; disabled?: boolean; accessibilityLabel?: string }) {
  return <Pressable accessibilityLabel={accessibilityLabel ?? label} accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.button, secondary && styles.secondary, destructive && styles.destructive, disabled && styles.disabled, pressed && !disabled && styles.pressed]}><Text style={[styles.buttonText, secondary && styles.secondaryText, destructive && styles.destructiveText]}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { flex: 1, paddingHorizontal: spacing.lg, paddingTop: spacing.xl + spacing.md },
  scroll: { flexGrow: 1, paddingHorizontal: spacing.lg, paddingTop: spacing.xl + spacing.md, paddingBottom: 48 },
  card: { backgroundColor: colors.surface, borderRadius: radius.md, borderColor: colors.border, borderWidth: 1, padding: spacing.md },
  stateRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  stateText: { color: colors.textMuted, lineHeight: 21 },
  errorBox: { backgroundColor: "#FCEBE8", borderRadius: radius.md, padding: spacing.md, gap: spacing.sm },
  errorText: { color: colors.danger, lineHeight: 21, fontWeight: "600" },
  empty: { alignItems: "center", paddingVertical: 44, gap: spacing.md },
  emptyTitle: { color: colors.text, fontSize: 21, fontWeight: "800" },
  pill: { alignSelf: "flex-start", backgroundColor: colors.primarySoft, color: colors.primary, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 5, fontSize: 12, fontWeight: "700" },
  warning: { backgroundColor: colors.attentionSoft, color: colors.attention },
  button: { backgroundColor: colors.primary, minHeight: 52, justifyContent: "center", alignItems: "center", borderRadius: radius.md, paddingHorizontal: 18 },
  buttonText: { color: "white", fontWeight: "800", fontSize: 16 },
  secondary: { backgroundColor: "transparent", borderColor: colors.primary, borderWidth: 1 },
  secondaryText: { color: colors.primary },
  destructive: { backgroundColor: "transparent", borderColor: colors.danger, borderWidth: 1 },
  destructiveText: { color: colors.danger },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.8 },
});
