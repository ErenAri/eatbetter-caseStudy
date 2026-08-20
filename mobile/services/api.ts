import { File } from "expo-file-system";

import { ApiErrorBody, DailySummary, Meal, MealEnvelope, MealList } from "../types/api";
import { HealthResponse } from "../types/health";
import { LocalImage } from "../types/meal";
import { API_BASE_URL } from "../utils/config";

const authorization = { Authorization: "Bearer dev-mobile-user" };
const jsonHeaders = { ...authorization, "Content-Type": "application/json" };
const FRIENDLY_ERRORS: Record<string, string> = {
  ANALYSIS_TEMPORARILY_UNAVAILABLE: "Meal analysis is temporarily unavailable.",
  UNRESOLVED_CLARIFICATIONS: "A few items still need review.",
  UNSUPPORTED_IMAGE: "Choose a JPEG, PNG, or WebP meal photo.",
  IMAGE_TOO_LARGE: "This photo is too large. Choose a smaller image.",
  VISION_UNSUPPORTED_IMAGE: "We couldn't read this photo. Try another one.",
  VISION_TIMEOUT: "Meal analysis took too long. Please try again.",
  VISION_RATE_LIMITED: "Meal analysis is busy right now. Please try again shortly.",
  VISION_UNAVAILABLE: "Meal recognition is temporarily unavailable. Please try again.",
  VISION_REFUSED: "This photo could not be analyzed. Choose a clear meal photo.",
  VISION_INVALID_RESPONSE: "Meal recognition returned an unusable result. Please try again.",
  VISION_IMAGE_UNAVAILABLE: "The uploaded photo is no longer available. Choose it again.",
  VISION_CONFIGURATION_ERROR: "Meal recognition is not configured on this server.",
  CANONICALIZATION_TIMEOUT: "Food matching took too long. Please try again.",
  CANONICALIZATION_RATE_LIMITED: "Food matching is busy right now. Please try again shortly.",
  CANONICALIZATION_UNAVAILABLE: "Food matching is temporarily unavailable.",
  CANONICALIZATION_REFUSED: "The food match could not be verified. Choose a food manually.",
  CANONICALIZATION_INVALID_RESPONSE: "The food match could not be verified. Choose a food manually.",
  CANONICALIZATION_INVALID_SELECTION: "The suggested food was invalid. Choose a food manually.",
  CANONICALIZATION_CONFIGURATION_ERROR: "Food matching is not configured on this server.",
  USDA_UNAVAILABLE: "Nutrition matching is temporarily unavailable.",
  USDA_TIMEOUT: "Nutrition matching took too long. Please try again.",
  USDA_RATE_LIMITED: "Nutrition matching is busy right now. Please try again shortly.",
  USDA_CONFIGURATION_ERROR: "USDA nutrition matching is not configured on this server.",
  USDA_AUTHENTICATION_FAILED: "USDA nutrition matching is unavailable because server access failed.",
  USDA_FOOD_NOT_FOUND: "That food is no longer available. Choose another match.",
  USDA_INCOMPLETE_NUTRITION: "That food lacks complete nutrition data. Choose another match.",
  USDA_INVALID_RESPONSE: "Nutrition data could not be verified. Try a different food match.",
  AI_NUTRITION_ERROR: "Nutrition estimation failed. Please try again.",
  AI_NUTRITION_CONFIGURATION: "Nutrition estimation is not configured on this server.",
  AI_NUTRITION_INVALID_RESPONSE: "Nutrition estimation returned an unusable result. Please try again.",
  AI_NUTRITION_TIMEOUT: "Nutrition estimation took too long. Please try again.",
  AI_NUTRITION_RATE_LIMITED: "Nutrition estimation is busy right now. Please try again shortly.",
  AI_NUTRITION_UNAVAILABLE: "Nutrition estimation is temporarily unavailable. Please try again.",
};

export class ApiError extends Error {
  constructor(public readonly code: string, public readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = init ? await fetch(`${API_BASE_URL}${path}`, init) : await fetch(`${API_BASE_URL}${path}`);
  } catch {
    throw new ApiError("OFFLINE", 0, "You're offline. Reconnect to continue.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const code = body.error?.code ?? "REQUEST_FAILED";
    throw new ApiError(code, response.status, FRIENDLY_ERRORS[code] ?? "Something went wrong. Please try again.");
  }
  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> { return request("/health"); }

export async function createMeal(input: { meal_request_id: string; logged_at: string; user_context: string | null }): Promise<Meal> {
  return (await request<MealEnvelope>("/api/v1/meals", { method: "POST", headers: jsonHeaders, body: JSON.stringify(input) })).meal;
}

export async function uploadMealImage(mealId: string, image: LocalImage): Promise<void> {
  const form = new FormData();
  form.append("image", new File(image.uri), image.fileName);
  await request(`/api/v1/meals/${mealId}/image`, { method: "POST", headers: authorization, body: form });
}

export async function analyzeMeal(mealId: string): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}/analysis`, { method: "POST", headers: authorization })).meal;
}

export async function getMeal(mealId: string): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}`, { headers: authorization })).meal;
}

export async function listMeals(date?: string): Promise<Meal[]> {
  const query = new URLSearchParams({ limit: "100" });
  if (date) query.set("date", date);
  return (await request<MealList>(`/api/v1/meals?${query.toString()}`, { headers: authorization })).items;
}

export async function getDailySummary(date: string, timezone: string): Promise<DailySummary> {
  return request(`/api/v1/daily-summary?date=${encodeURIComponent(date)}&timezone=${encodeURIComponent(timezone)}`, { headers: authorization });
}

export async function answerClarification(mealId: string, clarificationId: string, answer: { option_id: string } | { custom_grams: number }): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}/clarifications/${clarificationId}/answer`, { method: "POST", headers: jsonHeaders, body: JSON.stringify(answer) })).meal;
}

export async function updateMealItem(mealId: string, itemId: string, update: { candidate_rank?: number; portion_g?: number; preparation_method?: string | null }): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}/items/${itemId}`, { method: "PATCH", headers: jsonHeaders, body: JSON.stringify(update) })).meal;
}

export async function removeMealItem(mealId: string, itemId: string): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}/items/${itemId}`, { method: "DELETE", headers: authorization })).meal;
}

export async function addMealItem(mealId: string, query: string, portionG: number): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}/items`, { method: "POST", headers: jsonHeaders, body: JSON.stringify({ query, portion_g: portionG }) })).meal;
}

export async function replaceMealItem(mealId: string, itemId: string, query: string, portionG: number): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}/items/${itemId}/replacement`, { method: "POST", headers: jsonHeaders, body: JSON.stringify({ query, portion_g: portionG }) })).meal;
}

export async function deleteMeal(mealId: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/meals/${mealId}`, { method: "DELETE", headers: authorization });
  } catch {
    throw new ApiError("OFFLINE", 0, "You're offline. Reconnect to continue.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const code = body.error?.code ?? "REQUEST_FAILED";
    throw new ApiError(code, response.status, FRIENDLY_ERRORS[code] ?? "Something went wrong. Please try again.");
  }
}

export async function confirmMeal(mealId: string): Promise<Meal> {
  return (await request<MealEnvelope>(`/api/v1/meals/${mealId}/confirm`, { method: "POST", headers: authorization })).meal;
}

export async function createDemoMeal(): Promise<Meal> {
  return (await request<MealEnvelope>("/api/v1/dev/fixtures/review-meal", { method: "POST", headers: authorization })).meal;
}

export async function createCanonicalDemoMeal(): Promise<Meal> {
  return (await request<MealEnvelope>("/api/v1/dev/fixtures/canonical-review-meal", { method: "POST", headers: authorization })).meal;
}
