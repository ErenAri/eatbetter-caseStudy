import * as ImagePicker from "expo-image-picker";
import { useState } from "react";
import { Image, Linking, StyleSheet, Text, TextInput, View } from "react-native";
import { Button, ErrorState, Screen } from "../../components/Primitives";
import { colors, radius, spacing } from "../../theme/tokens";
import { LocalImage } from "../../types/meal";

function assetFrom(result: ImagePicker.ImagePickerResult): LocalImage | null {
  if (result.canceled) return null;
  const asset = result.assets[0];
  return asset ? { uri: asset.uri, mimeType: asset.mimeType ?? "image/jpeg", fileName: asset.fileName ?? `meal-${Date.now()}.jpg` } : null;
}

export function CaptureScreen({ image, context, busy, error, demoAvailable = __DEV__, onImage, onContext, onAnalyze, onDemo, onCanonicalDemo, onBack }: {
  image: LocalImage | null;
  context: string;
  busy: boolean;
  error: string | null;
  demoAvailable?: boolean;
  onImage: (image: LocalImage | null) => void;
  onContext: (value: string) => void;
  onAnalyze: () => void;
  onDemo: () => void;
  onCanonicalDemo?: () => void;
  onBack: () => void;
}) {
  const [cameraDenied, setCameraDenied] = useState(false);
  const camera = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    setCameraDenied(!permission.granted);
    if (!permission.granted) return;
    const selected = assetFrom(await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.8, cameraType: ImagePicker.CameraType.back }));
    if (selected) onImage(selected);
  };
  const library = async () => {
    const selected = assetFrom(await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.8 }));
    if (selected) { setCameraDenied(false); onImage(selected); }
  };
  return <Screen scroll>
    <Text accessibilityRole="button" onPress={onBack} style={styles.back}>‹ Today</Text>
    <Text style={styles.title}>Log a meal</Text>
    <Text style={styles.subtitle}>Take a clear photo, then add anything the camera cannot see.</Text>
    {cameraDenied ? <ErrorState message="Camera access is needed to take a meal photo." action={<View style={styles.permissionActions}><Button label="Open Settings" onPress={() => void Linking.openSettings()} /><Button label="Choose Photo Instead" onPress={() => void library()} secondary /></View>} /> : null}
    <View style={styles.photo}>{image ? <Image accessibilityLabel="Meal photo preview" source={{ uri: image.uri }} style={styles.preview} /> : <Text style={styles.placeholder}>Your meal photo</Text>}</View>
    {image ? <View style={styles.row}><View style={styles.flex}><Button label="Retake" onPress={() => { onImage(null); void camera(); }} secondary /></View><View style={styles.flex}><Button label="Choose another" onPress={() => void library()} secondary /></View></View> : <><Button accessibilityLabel="Take Photo" label="Take Photo" onPress={() => void camera()} /><View style={styles.space} /><Button label="Choose from Photos" onPress={() => void library()} secondary /></>}
    <Text style={styles.label}>Add context <Text style={styles.optional}>(optional)</Text></Text>
    <TextInput accessibilityLabel="Optional meal context" multiline maxLength={1000} placeholder="e.g. Chicken was cooked with olive oil" placeholderTextColor={colors.textMuted} value={context} onChangeText={onContext} style={styles.input} />
    {error ? <ErrorState message={error} /> : null}
    <Button label={busy ? "Starting analysis…" : "Analyze meal"} onPress={onAnalyze} disabled={!image || busy} />
    {demoAvailable ? <View style={styles.demo}><Text style={styles.demoLabel}>Development demo</Text><Button label="Open portion review demo" onPress={onDemo} secondary disabled={busy} />{onCanonicalDemo ? <Button label="Open food-choice demo" onPress={onCanonicalDemo} secondary disabled={busy} /> : null}</View> : null}
  </Screen>;
}

const styles = StyleSheet.create({ back: { color: colors.primary, fontWeight: "800", marginBottom: spacing.md, minHeight: 32 }, title: { color: colors.text, fontSize: 34, fontWeight: "900" }, subtitle: { color: colors.textMuted, lineHeight: 21, marginTop: spacing.xs }, photo: { height: 250, backgroundColor: "#E6E8E2", borderRadius: radius.lg, marginVertical: spacing.lg, overflow: "hidden", alignItems: "center", justifyContent: "center" }, preview: { width: "100%", height: "100%" }, placeholder: { color: colors.textMuted, fontWeight: "700" }, row: { flexDirection: "row", gap: spacing.sm }, flex: { flex: 1 }, space: { height: spacing.sm }, label: { color: colors.text, fontWeight: "800", marginTop: spacing.lg, marginBottom: spacing.sm }, optional: { color: colors.textMuted, fontWeight: "500" }, input: { minHeight: 96, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: spacing.md, color: colors.text, textAlignVertical: "top", marginBottom: spacing.md }, permissionActions: { gap: spacing.sm }, demo: { borderTopWidth: 1, borderTopColor: colors.border, marginTop: spacing.lg, paddingTop: spacing.md, gap: spacing.sm }, demoLabel: { color: colors.textMuted, fontSize: 12, textTransform: "uppercase", fontWeight: "800", letterSpacing: 1 } });
