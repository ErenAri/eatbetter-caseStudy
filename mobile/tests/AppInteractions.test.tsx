import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import App from "../App";
import * as api from "../services/api";
import { baseMeal, canonicalClarification, portionClarification, reviewMeal } from "./fixtures";

jest.mock("../hooks/useBackendHealth", () => ({ useBackendHealth: () => "connected" }));
jest.mock("../services/api", () => {
  const actual = jest.requireActual("../services/api");
  return {
    ...actual,
    listMeals: jest.fn(), getDailySummary: jest.fn(), getMeal: jest.fn(),
    answerClarification: jest.fn(), confirmMeal: jest.fn(),
    createMeal: jest.fn(), uploadMealImage: jest.fn(), analyzeMeal: jest.fn(),
    updateMealItem: jest.fn(), removeMealItem: jest.fn(), addMealItem: jest.fn(), replaceMealItem: jest.fn(), deleteMeal: jest.fn(), createDemoMeal: jest.fn(), createCanonicalDemoMeal: jest.fn(),
  };
});
const mocked = api as jest.Mocked<typeof api>;

beforeEach(() => {
  jest.clearAllMocks();
  mocked.getDailySummary.mockResolvedValue({ date: "2026-08-18", timezone: "UTC", totals: baseMeal.totals, meals: [baseMeal] });
});

test("candidate tap calls the clarification answer API", async () => {
  const meal = reviewMeal(canonicalClarification);
  mocked.listMeals.mockResolvedValue([meal]);
  mocked.getMeal.mockResolvedValue(meal);
  mocked.answerClarification.mockResolvedValue({ ...meal, clarifications: [] });
  const view = await render(<App />);
  const card = await view.findByRole("button", { name: /Chicken breast, grilled.*Needs review/ });
  await act(async () => { fireEvent.press(card); });
  await waitFor(() => expect(mocked.getMeal).toHaveBeenCalledWith("meal-1"));
  await act(async () => { fireEvent.press(await view.findByRole("button", { name: "White rice, cooked" })); });
  await waitFor(() => expect(mocked.answerClarification).toHaveBeenCalledWith("meal-1", "canonical-1", { option_id: "candidate-1" }));
});

test("portion option calls the clarification answer API", async () => {
  const meal = reviewMeal(portionClarification);
  mocked.listMeals.mockResolvedValue([meal]);
  mocked.getMeal.mockResolvedValue(meal);
  mocked.answerClarification.mockResolvedValue({ ...meal, clarifications: [] });
  const view = await render(<App />);
  await act(async () => { fireEvent.press(await view.findByRole("button", { name: /Chicken breast, grilled.*Needs review/ })); });
  await waitFor(() => expect(mocked.getMeal).toHaveBeenCalledWith("meal-1"));
  await act(async () => { fireEvent.press(await view.findByRole("button", { name: "About this amount" })); });
  await waitFor(() => expect(mocked.answerClarification).toHaveBeenCalledWith("meal-1", "portion-1", { option_id: "estimated" }));
});

test("save calls confirmation endpoint for a resolved meal", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  mocked.listMeals.mockResolvedValue([meal]);
  mocked.getMeal.mockResolvedValue(meal);
  mocked.confirmMeal.mockResolvedValue(baseMeal);
  const view = await render(<App />);
  await act(async () => { fireEvent.press(await view.findByRole("button", { name: /Chicken breast, grilled.*Needs review/ })); });
  await waitFor(() => expect(mocked.getMeal).toHaveBeenCalledWith("meal-1"));
  await act(async () => { fireEvent.press(await view.findByRole("button", { name: "Save meal" })); });
  await waitFor(() => expect(mocked.confirmMeal).toHaveBeenCalledWith("meal-1"));
});

test("remove action calls the item delete API method", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  mocked.listMeals.mockResolvedValue([meal]);
  mocked.getMeal.mockResolvedValue(meal);
  mocked.removeMealItem.mockResolvedValue({ ...meal, items: [{ ...meal.items[0]!, is_removed: true, review_status: "REMOVED" }] });
  const view = await render(<App />);
  await act(async () => { fireEvent.press(await view.findByRole("button", { name: /Chicken breast, grilled.*Needs review/ })); });
  await waitFor(() => expect(mocked.getMeal).toHaveBeenCalledWith("meal-1"));
  await act(async () => { fireEvent.press(await view.findByRole("button", { name: "Remove" })); });
  await waitFor(() => expect(mocked.removeMealItem).toHaveBeenCalledWith("meal-1", "item-1"));
});

test("opens an uploaded shell as incomplete and resumes an attached image", async () => {
  const incomplete = { ...baseMeal, status: "UPLOADED" as const, confirmed_at: null, image_attached: true, items: [], totals: { calories_kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 } };
  const reviewed = reviewMeal(portionClarification);
  mocked.listMeals.mockResolvedValue([incomplete]);
  mocked.analyzeMeal.mockResolvedValue(reviewed);
  const view = await render(<App />);

  await act(async () => { fireEvent.press(await view.findByRole("button", { name: /Meal photo.*Incomplete/ })); });
  expect(await view.findByText("Incomplete meal")).toBeTruthy();
  expect(view.queryByText("Meal saved")).toBeNull();
  await act(async () => { fireEvent.press(view.getByRole("button", { name: "Resume analysis" })); });

  await waitFor(() => expect(mocked.analyzeMeal).toHaveBeenCalledWith("meal-1"));
  expect(await view.findByText("Review meal")).toBeTruthy();
});
