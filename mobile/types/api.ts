export type MealStatus = "UPLOADED" | "ANALYZING" | "NEEDS_REVIEW" | "CONFIRMED" | "FAILED_RETRYABLE" | "FAILED_PERMANENT";
export type ReviewStatus = "NOT_READY" | "READY" | "REMOVED" | "NEEDS_REVIEW" | "NEEDS_IDENTITY" | "NEEDS_PORTION" | "NEEDS_HIDDEN_INGREDIENT";

export type NutritionTotals = { calories_kcal: number; protein_g: number; carbs_g: number; fat_g: number };
export type Candidate = { rank: number; source: string; food_id: string; name: string; display_name: string };

export type MealItem = {
  id: string;
  position: number;
  observed_name: string;
  normalized_name: string | null;
  preparation_method: string | null;
  canonical: { source: string; food_id: string; name: string } | null;
  candidates: Candidate[];
  portion: { min_g: number | null; max_g: number | null; confirmed_g: number | null; resolution_source: "AUTO_ESTIMATE" | "USER" | "USER_HOUSEHOLD_UNIT" | null };
  confidence: { canonical: number | null };
  requires_clarification: boolean;
  clarification_resolved: boolean;
  is_removed: boolean;
  is_user_added: boolean;
  nutrition: NutritionTotals | null;
  review_status: ReviewStatus;
};

export type ClarificationStatus = "PENDING" | "ANSWERED" | "DISMISSED";
type ClarificationBase<TType extends string, TValue> = {
  id: string;
  meal_item_id: string | null;
  type: TType;
  question: string;
  options: Array<{ id: string; label: string; value: TValue }>;
  reason_codes: string[];
  status: ClarificationStatus;
  answer: Record<string, unknown> | null;
  created_at: string;
  answered_at: string | null;
  blocking: boolean;
  resolution_satisfied: boolean;
};
export type CanonicalClarification = ClarificationBase<"CANONICAL_SELECTION", { candidate_rank: number }>;
export type PortionClarification = ClarificationBase<"PORTION", { grams: string; household_unit?: string }>;
export type HiddenIngredientClarification = ClarificationBase<"HIDDEN_INGREDIENT", { presence: "NO" | "YES" | "NOT_SURE"; name: string }>;
export type FoodIdentityClarification = ClarificationBase<"FOOD_IDENTITY", { action: "MANUAL_SEARCH" | "REMOVE_ITEM" }>;
export type Clarification = CanonicalClarification | PortionClarification | HiddenIngredientClarification | FoodIdentityClarification;

export type Correction = { id: string; meal_item_id: string | null; field_name: string; predicted_value: unknown; corrected_value: unknown; correction_source: string; created_at: string };
export type Meal = {
  id: string;
  meal_request_id: string;
  status: MealStatus;
  review_status: ReviewStatus;
  image_attached: boolean;
  user_context: string | null;
  logged_at: string;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
  failure_code: string | null;
  items: MealItem[];
  clarifications: Clarification[];
  corrections: Correction[];
  totals: NutritionTotals;
};
export type MealEnvelope = { meal: Meal };
export type MealList = { items: Meal[]; next_cursor: string | null };
export type DailySummary = { date: string; timezone: string; totals: NutritionTotals; meals: Meal[] };
export type ApiErrorBody = { error?: { code?: string; message?: string; request_id?: string; details?: unknown } };
