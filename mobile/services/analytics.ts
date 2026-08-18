export type ProductEvent =
  | "meal_capture_started"
  | "meal_analysis_requested"
  | "meal_review_opened"
  | "clarification_viewed"
  | "clarification_answered"
  | "meal_item_corrected"
  | "meal_confirmed"
  | "meal_abandoned";

export function track(event: ProductEvent, fields: { mealId?: string; clarificationType?: string } = {}): void {
  // Provider-neutral seam: intentionally no-op until a privacy-reviewed analytics sink is selected.
  void event;
  void fields;
}
