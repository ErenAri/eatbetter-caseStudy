import { Clarification, Meal, MealItem } from "../types/api";

export const readyItem: MealItem = {
  id: "item-1", position: 0, observed_name: "chicken breast", normalized_name: "chicken breast", preparation_method: "grilled",
  canonical: { source: "USDA", food_id: "1", name: "Chicken breast, grilled" },
  candidates: [{ rank: 1, source: "USDA", food_id: "1", name: "Chicken breast, grilled", display_name: "Chicken breast, grilled · USDA foundation food" }],
  portion: { min_g: 140, max_g: 180, confirmed_g: 160, resolution_source: "AUTO_ESTIMATE" },
  confidence: { canonical: null }, requires_clarification: false, clarification_resolved: true, is_removed: false, is_user_added: false,
  nutrition: { calories_kcal: 264, protein_g: 49.6, carbs_g: 0, fat_g: 5.8 }, review_status: "READY",
};
export const baseMeal: Meal = {
  id: "meal-1", meal_request_id: "request-1", status: "CONFIRMED", review_status: "READY", image_attached: true, user_context: null,
  logged_at: "2026-08-18T10:00:00Z", created_at: "2026-08-18T10:00:00Z", updated_at: "2026-08-18T10:00:00Z", confirmed_at: "2026-08-18T10:02:00Z", failure_code: null,
  items: [readyItem], clarifications: [], corrections: [], totals: { calories_kcal: 264, protein_g: 49.6, carbs_g: 0, fat_g: 5.8 },
};
export function reviewMeal(clarification?: Clarification): Meal {
  return { ...baseMeal, status: "NEEDS_REVIEW", confirmed_at: null, review_status: clarification?.type === "PORTION" ? "NEEDS_PORTION" : clarification ? "NEEDS_IDENTITY" : "READY", clarifications: clarification ? [clarification] : [], items: clarification?.meal_item_id ? [{ ...readyItem, id: clarification.meal_item_id, review_status: clarification.type === "PORTION" ? "NEEDS_PORTION" : "NEEDS_IDENTITY", nutrition: clarification.type === "PORTION" ? null : readyItem.nutrition, portion: clarification.type === "PORTION" ? { ...readyItem.portion, confirmed_g: null, resolution_source: null } : readyItem.portion, requires_clarification: true, clarification_resolved: false }] : [readyItem] };
}
const clarificationBase = { meal_item_id: "item-1", reason_codes: [], status: "PENDING" as const, answer: null, created_at: "2026-08-18T10:01:00Z", answered_at: null, blocking: true, resolution_satisfied: false };
export const portionClarification: Clarification = { ...clarificationBase, id: "portion-1", type: "PORTION", question: "How much rice was there?", options: [{ id: "estimated", label: "About this amount", value: { grams: "180" } }] };
export const canonicalClarification: Clarification = { ...clarificationBase, id: "canonical-1", type: "CANONICAL_SELECTION", question: "Which food best matches this?", options: [{ id: "candidate-1", label: "White rice, cooked", value: { candidate_rank: 1 } }] };
export const hiddenClarification: Clarification = { ...clarificationBase, id: "hidden-1", meal_item_id: null, type: "HIDDEN_INGREDIENT", question: "Was cooking oil used?", options: [{ id: "no", label: "No", value: { presence: "NO", name: "cooking oil" } }, { id: "yes", label: "Yes", value: { presence: "YES", name: "cooking oil" } }, { id: "not-sure", label: "Not sure", value: { presence: "NOT_SURE", name: "cooking oil" } }] };
