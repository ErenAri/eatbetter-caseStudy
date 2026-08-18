import { useCallback, useEffect, useRef, useState } from "react";
import { StatusBar } from "expo-status-bar";
import { AnalysisScreen } from "./features/meal-capture/AnalysisScreen";
import { CaptureScreen } from "./features/meal-capture/CaptureScreen";
import { MealDetailScreen } from "./features/meal-history/MealDetailScreen";
import { TodayScreen } from "./features/meal-history/TodayScreen";
import { ReviewScreen } from "./features/meal-review/ReviewScreen";
import { useBackendHealth } from "./hooks/useBackendHealth";
import {
  ApiError,
  addMealItem,
  analyzeMeal,
  answerClarification,
  confirmMeal,
  createDemoMeal,
  createCanonicalDemoMeal,
  createMeal,
  getDailySummary,
  getMeal,
  listMeals,
  removeMealItem,
  updateMealItem,
  uploadMealImage,
} from "./services/api";
import { track } from "./services/analytics";
import { Meal, MealItem, NutritionTotals } from "./types/api";
import { LocalImage, MealAttempt } from "./types/meal";

type Route = "today" | "capture" | "analysis" | "review" | "detail";
const emptyTotals: NutritionTotals = { calories_kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 };
function uuid(): string { return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => { const value = Math.floor(Math.random() * 16); return (character === "x" ? value : (value & 0x3) | 0x8).toString(16); }); }
function localDate(): string { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`; }
function message(reason: unknown, fallback: string): string { return reason instanceof Error ? reason.message : fallback; }

export default function App() {
  const [route, setRoute] = useState<Route>("today");
  const [meals, setMeals] = useState<Meal[]>([]);
  const [totals, setTotals] = useState<NutritionTotals>(emptyTotals);
  const [meal, setMeal] = useState<Meal | null>(null);
  const [image, setImage] = useState<LocalImage | null>(null);
  const [context, setContext] = useState("");
  const [attempt, setAttempt] = useState<MealAttempt | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [todayLoading, setTodayLoading] = useState(true);
  const [todayError, setTodayError] = useState<string | null>(null);
  const operation = useRef(0);
  const healthStatus = useBackendHealth();

  const refreshToday = useCallback(async () => {
    setTodayLoading(true); setTodayError(null);
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      const date = localDate();
      const [allMeals, summary] = await Promise.all([listMeals(date), getDailySummary(date, timezone)]);
      setMeals(allMeals); setTotals(summary.totals);
    } catch (reason) { setTodayError(message(reason, "Couldn't load today's meals.")); }
    finally { setTodayLoading(false); }
  }, []);
  useEffect(() => { void refreshToday(); }, [refreshToday]);
  useEffect(() => {
    if (route !== "review" || !meal) return;
    const current = meal.clarifications.find((value) => value.blocking && !value.resolution_satisfied);
    if (current) track("clarification_viewed", { mealId: meal.id, clarificationType: current.type });
  }, [route, meal]);

  const beginCapture = () => {
    operation.current += 1;
    setAttempt({ requestId: uuid(), mealId: null, imageAttached: false });
    setImage(null); setContext(""); setMeal(null); setError(null); setRoute("capture");
    track("meal_capture_started");
  };

  const submitAnalysis = async () => {
    if (!image || !attempt || busyKey === "analysis") return;
    const token = ++operation.current;
    setBusyKey("analysis"); setError(null); setRoute("analysis"); track("meal_analysis_requested", { mealId: attempt.mealId ?? undefined });
    let active = attempt;
    try {
      if (!active.mealId) {
        const created = await createMeal({ meal_request_id: active.requestId, logged_at: new Date().toISOString(), user_context: context.trim() || null });
        active = { ...active, mealId: created.id }; setAttempt(active);
      }
      const mealId = active.mealId;
      if (!mealId) throw new Error("Meal creation did not return an identifier.");
      if (!active.imageAttached) {
        await uploadMealImage(mealId, image);
        active = { ...active, imageAttached: true }; setAttempt(active);
      }
      const analyzed = await analyzeMeal(mealId);
      if (operation.current !== token) return;
      setMeal(analyzed); setRoute("review"); track("meal_review_opened", { mealId: analyzed.id });
    } catch (reason) { if (operation.current === token) setError(message(reason, "We couldn't analyze this meal.")); }
    finally { if (operation.current === token) setBusyKey(null); }
  };

  const mutate = async (key: string, action: () => Promise<Meal>) => {
    if (busyKey) return;
    setBusyKey(key); setError(null);
    try { setMeal(await action()); }
    catch (reason) { setError(message(reason, "That change couldn't be saved. Try again.")); }
    finally { setBusyKey(null); }
  };

  const answer = (clarificationId: string, value: { option_id: string } | { custom_grams: number }) => {
    if (!meal) return;
    const clarification = meal.clarifications.find((entry) => entry.id === clarificationId);
    void mutate(clarificationId, async () => {
      const next = await answerClarification(meal.id, clarificationId, value);
      track("clarification_answered", { mealId: meal.id, clarificationType: clarification?.type });
      return next;
    });
  };
  const update = (item: MealItem, value: { candidate_rank?: number; portion_g?: number; preparation_method?: string | null }) => { if (meal) void mutate(item.id, async () => { const next = await updateMealItem(meal.id, item.id, value); track("meal_item_corrected", { mealId: meal.id }); return next; }); };
  const remove = (item: MealItem) => { if (meal) void mutate(item.id, async () => { const next = await removeMealItem(meal.id, item.id); track("meal_item_corrected", { mealId: meal.id }); return next; }); };
  const add = (query: string, grams: number) => { if (meal) void mutate("add", () => addMealItem(meal.id, query, grams)); };

  const confirm = async () => {
    if (!meal || busyKey) return;
    setBusyKey("confirm"); setError(null);
    try { const confirmed = await confirmMeal(meal.id); setMeal(confirmed); setRoute("detail"); track("meal_confirmed", { mealId: meal.id }); await refreshToday(); }
    catch (reason) {
      if (reason instanceof ApiError && reason.code === "UNRESOLVED_CLARIFICATIONS") setMeal(await getMeal(meal.id));
      setError(message(reason, "The meal couldn't be saved."));
    } finally { setBusyKey(null); }
  };

  const openMeal = async (selected: Meal) => {
    setMeal(selected); setError(null); setRoute(selected.status === "NEEDS_REVIEW" ? "review" : "detail");
    if (selected.status === "NEEDS_REVIEW") { track("meal_review_opened", { mealId: selected.id }); try { setMeal(await getMeal(selected.id)); } catch { /* preserve list snapshot */ } }
  };
  const home = () => { operation.current += 1; setRoute("today"); setError(null); setBusyKey(null); void refreshToday(); };
  const chooseAnother = () => { operation.current += 1; setAttempt({ requestId: uuid(), mealId: null, imageAttached: false }); setImage(null); setError(null); setRoute("capture"); };
  const demo = async (canonical = false) => { if (busyKey) return; setBusyKey("demo"); setError(null); try { const fixture = canonical ? await createCanonicalDemoMeal() : await createDemoMeal(); setMeal(fixture); setRoute("review"); track("meal_review_opened", { mealId: fixture.id }); } catch (reason) { setError(message(reason, "The development demo is unavailable.")); } finally { setBusyKey(null); } };

  return <><StatusBar style="dark" />
    {route === "today" ? <TodayScreen meals={meals} totals={totals} loading={todayLoading} error={todayError} healthStatus={healthStatus} onRetry={() => void refreshToday()} onLog={beginCapture} onOpen={(selected) => void openMeal(selected)} /> : null}
    {route === "capture" ? <CaptureScreen image={image} context={context} busy={busyKey !== null} error={error} onImage={setImage} onContext={setContext} onAnalyze={() => void submitAnalysis()} onDemo={() => void demo()} onCanonicalDemo={() => void demo(true)} onBack={home} /> : null}
    {route === "analysis" ? <AnalysisScreen error={error} onRetry={() => void submitAnalysis()} onChooseAnother={chooseAnother} onCancel={() => { track("meal_abandoned", { mealId: attempt?.mealId ?? undefined }); home(); }} /> : null}
    {route === "review" && meal ? <ReviewScreen meal={meal} busyKey={busyKey} error={error} onAnswer={answer} onUpdate={update} onRemove={remove} onAdd={add} onConfirm={() => void confirm()} onBack={home} /> : null}
    {route === "detail" && meal ? <MealDetailScreen meal={meal} onBack={home} /> : null}
  </>;
}
