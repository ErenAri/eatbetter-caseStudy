import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button, ErrorState, LoadingState, Screen } from "../../components/Primitives";
import { colors, spacing } from "../../theme/tokens";

const messages = ["Identifying visible foods", "Matching verified nutrition", "Checking uncertain portions"];
export type AnalysisPhase = "uploading" | "analyzing";
export function AnalysisScreen({ phase = "analyzing", error, onRetry, onChooseAnother, onCancel }: { phase?: AnalysisPhase; error: string | null; onRetry: () => void; onChooseAnother: () => void; onCancel: () => void }) {
  const [message, setMessage] = useState(0);
  useEffect(() => {
    setMessage(0);
    if (error || phase === "uploading") return;
    const nutrition = setTimeout(() => setMessage(1), 8000);
    const uncertainty = setTimeout(() => setMessage(2), 18000);
    return () => { clearTimeout(nutrition); clearTimeout(uncertainty); };
  }, [error, phase]);
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
        <LoadingState message={phase === "uploading" ? "Uploading photo securely" : messages[message] ?? messages[0]} />
        <Text style={styles.progress}>{phase === "uploading" ? "Preparing analysis" : `Step ${message + 1} of 3`}</Text>
        <Text style={styles.body}>Live analysis can take around 30 seconds. You can leave safely; the attempt remains recoverable.</Text>
        <Button label="Cancel" onPress={onCancel} secondary />
      </>}
    </View>
  </Screen>;
}
const styles = StyleSheet.create({ center: { flex: 1, justifyContent: "center", gap: spacing.md }, title: { color: colors.text, fontSize: 30, lineHeight: 37, fontWeight: "900" }, progress: { color: colors.primary, fontWeight: "800" }, body: { color: colors.textMuted, lineHeight: 22, marginBottom: spacing.sm } });
