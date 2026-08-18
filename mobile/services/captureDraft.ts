import { File, Paths } from "expo-file-system";

import { LocalImage, MealAttempt } from "../types/meal";

export type CaptureDraft = { attempt: MealAttempt; context: string; image: LocalImage | null };

const draftFile = () => new File(Paths.document, "eatbetter-capture-draft.json");

export async function loadCaptureDraft(): Promise<CaptureDraft | null> {
  try {
    const file = draftFile();
    if (!file.exists) return null;
    const value = JSON.parse(await file.text()) as Partial<CaptureDraft>;
    if (!value.attempt?.requestId || typeof value.context !== "string") return null;
    return { attempt: value.attempt, context: value.context, image: value.image ?? null };
  } catch {
    return null;
  }
}

export async function saveCaptureDraft(value: CaptureDraft): Promise<void> {
  try {
    const file = draftFile();
    if (!file.exists) file.create({ intermediates: true });
    file.write(JSON.stringify(value));
  } catch {
    // Draft persistence is a recovery aid; capture remains usable if storage is unavailable.
  }
}

export async function clearCaptureDraft(): Promise<void> {
  try {
    const file = draftFile();
    if (file.exists) file.delete();
  } catch {
    // The server-side incomplete-attempt state remains the fallback recovery path.
  }
}
