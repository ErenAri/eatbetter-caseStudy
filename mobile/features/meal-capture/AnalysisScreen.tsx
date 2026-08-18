import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button, ErrorState, LoadingState, Screen } from "../../components/Primitives";
import { colors, spacing } from "../../theme/tokens";

const messages = ["Identifying foods", "Matching nutrition data", "Checking uncertain portions"];
export function AnalysisScreen({ error, onRetry, onChooseAnother, onCancel }: { error: string | null; onRetry: () => void; onChooseAnother: () => void; onCancel: () => void }) {
  const [message, setMessage] = useState(0);
  useEffect(() => {
    if (error) return;
    const timer = setInterval(() => setMessage((value) => (value + 1) % messages.length), 1800);
    return () => clearInterval(timer);
  }, [error]);
  return <Screen>
    <View style={styles.center}>
      {error ? <>
        <Text style={styles.title}>We couldn't analyze this meal.</Text>
        <Text style={styles.body}>Your photo is still available.</Text>
        <ErrorState message={error} />
        <Button label="Try again" onPress={onRetry} />
        <Button label="Choose another photo" onPress={onChooseAnother} secondary />
      </> : <>
        <Text style={styles.title}>Analyzing your meal…</Text>
        <LoadingState message={messages[message] ?? messages[0]} />
        <Text style={styles.body}>This can take a few seconds. We'll only ask about details that could change your meal.</Text>
        <Button label="Cancel" onPress={onCancel} secondary />
      </>}
    </View>
  </Screen>;
}
const styles = StyleSheet.create({ center: { flex: 1, justifyContent: "center", gap: spacing.md }, title: { color: colors.text, fontSize: 30, lineHeight: 37, fontWeight: "900" }, body: { color: colors.textMuted, lineHeight: 22, marginBottom: spacing.sm } });
