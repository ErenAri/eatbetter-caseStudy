import { clearCaptureDraft, loadCaptureDraft, saveCaptureDraft } from "../services/captureDraft";

test("capture drafts survive reload and can be cleared", async () => {
  await clearCaptureDraft();
  const draft = {
    attempt: { requestId: "request-1", mealId: null, imageAttached: false },
    context: "cooked with oil",
    image: null,
  };

  await saveCaptureDraft(draft);
  await expect(loadCaptureDraft()).resolves.toEqual(draft);

  await clearCaptureDraft();
  await expect(loadCaptureDraft()).resolves.toBeNull();
});
