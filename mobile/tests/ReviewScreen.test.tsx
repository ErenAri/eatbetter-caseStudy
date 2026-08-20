import { act, fireEvent, render } from "@testing-library/react-native";
import { Alert } from "react-native";
import { ReviewScreen } from "../features/meal-review/ReviewScreen";
import { MealItem } from "../types/api";
import { baseMeal, canonicalClarification, hiddenClarification, portionClarification, readyItem, reviewMeal } from "./fixtures";

const props = { busyKey: null, error: null, onAnswer: jest.fn(), onUpdate: jest.fn().mockResolvedValue(true), onRemove: jest.fn(), onAdd: jest.fn().mockResolvedValue(true), onReplace: jest.fn().mockResolvedValue(true), onConfirm: jest.fn(), onBack: jest.fn() };
test("resolved item shows Looks good and enables save", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const view = await render(<ReviewScreen meal={meal} {...props} />);
  expect(view.getByText("✓ Looks good")).toBeTruthy();
  expect(view.getByRole("button", { name: "Save meal" }).props.accessibilityState.disabled).toBe(false);
});

test("portion clarification submits the stored option and disables save", async () => {
  const onAnswer = jest.fn();
  const view = await render(<ReviewScreen meal={reviewMeal(portionClarification)} {...props} onAnswer={onAnswer} />);
  expect(view.getByText("About how much rice did you eat?")).toBeTruthy();
  fireEvent.press(view.getByRole("button", { name: "About 180 g" }));
  expect(onAnswer).toHaveBeenCalledWith("portion-1", { option_id: "estimated" });
  expect(view.getByRole("button", { name: /Review 1 item/ }).props.accessibilityState.disabled).toBe(true);
});

test("canonical clarification renders readable candidate and submits option id", async () => {
  const onAnswer = jest.fn();
  const view = await render(<ReviewScreen meal={reviewMeal(canonicalClarification)} {...props} onAnswer={onAnswer} />);
  fireEvent.press(view.getByRole("button", { name: "White rice, cooked" }));
  expect(onAnswer).toHaveBeenCalledWith("canonical-1", { option_id: "candidate-1" });
  expect(view.queryByText(/rank 1/i)).toBeNull();
});

test("hidden ingredient clarification avoids claiming the photo confirms hidden use", async () => {
  const view = await render(<ReviewScreen meal={reviewMeal(hiddenClarification)} {...props} />);
  expect(view.getByText("Was cooking oil used in a way the photo may not show?")).toBeTruthy();
  expect(view.getByText(/photo alone cannot confirm hidden ingredients/i)).toBeTruthy();
  expect(view.getByRole("button", { name: "Not sure" })).toBeTruthy();
});

test("remove food requires confirmation before delegating the item action", async () => {
  const onRemove = jest.fn();
  const alert = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const view = await render(<ReviewScreen meal={meal} {...props} onRemove={onRemove} />);
  fireEvent.press(view.getByRole("button", { name: "Remove" }));
  expect(onRemove).not.toHaveBeenCalled();
  expect(alert).toHaveBeenCalledWith(
    "Remove this food?",
    expect.stringContaining("excluded from the saved meal"),
    expect.any(Array),
  );
  const buttons = alert.mock.calls[0]?.[2];
  buttons?.find((button) => button.text === "Remove")?.onPress?.();
  expect(onRemove).toHaveBeenCalledWith(meal.items[0]);
  alert.mockRestore();
});

test("ignores pending blockers that belong to removed items", async () => {
  const removed = { ...readyItem, id: "removed", is_removed: true, review_status: "REMOVED" as const };
  const stale = { ...portionClarification, meal_item_id: "removed" };
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null, items: [readyItem, removed], clarifications: [stale] };

  const view = await render(<ReviewScreen meal={meal} {...props} />);

  expect(view.queryByText(stale.question)).toBeNull();
  expect(view.getByRole("button", { name: "Save meal" }).props.accessibilityState.disabled).toBe(false);
});

test("Search for another food opens replacement and replaces the original item", async () => {
  const onReplace = jest.fn().mockResolvedValue(true);
  const meal = reviewMeal(canonicalClarification);
  const view = await render(<ReviewScreen meal={meal} {...props} onReplace={onReplace} />);

  await act(async () => { fireEvent.press(view.getByRole("button", { name: "Search for another food" })); });
  await act(async () => { fireEvent.changeText(view.getByLabelText("Food search"), "brown rice"); });
  await act(async () => { fireEvent.changeText(view.getByLabelText("Food amount in grams"), "150"); });
  await act(async () => { fireEvent.press(view.getByRole("button", { name: "Replace food" })); });

  expect(onReplace).toHaveBeenCalledWith(meal.items[0], "brown rice", 150);
});

test("ordinary amount editors require positive finite grams", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const view = await render(<ReviewScreen meal={meal} {...props} />);
  await act(async () => { fireEvent.press(view.getByRole("button", { name: "Change amount" })); });

  await act(async () => { fireEvent.changeText(view.getByLabelText("Amount in grams"), "0"); });
  expect(view.getByRole("button", { name: "Save amount" }).props.accessibilityState.disabled).toBe(true);
  await act(async () => { fireEvent.changeText(view.getByLabelText("Amount in grams"), "Infinity"); });
  expect(view.getByRole("button", { name: "Save amount" }).props.accessibilityState.disabled).toBe(true);
});

test("meal photo renders as a thumbnail when supplied, and nothing when absent", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const withPhoto = await render(<ReviewScreen meal={meal} image={{ uri: "file:///cache/meal.jpg", mimeType: "image/jpeg", fileName: "meal.jpg" }} {...props} />);
  expect(withPhoto.getByLabelText("Meal photo")).toBeTruthy();

  const withoutPhoto = await render(<ReviewScreen meal={meal} {...props} />);
  expect(withoutPhoto.queryByLabelText("Meal photo")).toBeNull();
});

test("running total reflects meal.totals and reads as final once every item is ready", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const view = await render(<ReviewScreen meal={meal} {...props} />);
  expect(view.getByLabelText("264 calories, 50 grams protein, 0 grams carbs, 6 grams fat")).toBeTruthy();
  expect(view.getByText("Meal total")).toBeTruthy();
});

test("running total is marked partial while foods are still unresolved", async () => {
  const meal = { ...reviewMeal(portionClarification), totals: { calories_kcal: 120, protein_g: 10, carbs_g: 5, fat_g: 3 } };
  const view = await render(<ReviewScreen meal={meal} {...props} />);
  expect(view.getByText("120 kcal")).toBeTruthy();
  expect(view.getByText("Only includes foods confirmed so far")).toBeTruthy();
});

test("header count includes items with anticipated questions that have no blocker yet", async () => {
  const base = reviewMeal(portionClarification);
  const anticipatedItem: MealItem = { ...readyItem, id: "item-2", review_status: "NEEDS_PORTION", nutrition: null, portion: { ...readyItem.portion, confirmed_g: null, resolution_source: null } };
  const meal = { ...base, items: [...base.items, anticipatedItem] };
  const view = await render(<ReviewScreen meal={meal} {...props} />);
  expect(view.getByText("2 quick checks")).toBeTruthy();
  expect(view.getByText("Question 1 of 2")).toBeTruthy();
});

test("does not overstate the remaining count when only one question truly remains", async () => {
  const view = await render(<ReviewScreen meal={reviewMeal(portionClarification)} {...props} />);
  expect(view.getByText("1 quick check")).toBeTruthy();
  expect(view.getByText("Question 1 of 1")).toBeTruthy();
});

test("successful amount edit closes the editor while failure retains it", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const failed = jest.fn().mockResolvedValue(false);
  const view = await render(<ReviewScreen meal={meal} {...props} onUpdate={failed} />);
  await act(async () => { fireEvent.press(view.getByRole("button", { name: "Change amount" })); });
  await act(async () => { fireEvent.changeText(view.getByLabelText("Amount in grams"), "120"); });
  await act(async () => { fireEvent.press(view.getByRole("button", { name: "Save amount" })); });
  expect(view.getByLabelText("Amount in grams")).toBeTruthy();

  await act(async () => { view.rerender(<ReviewScreen meal={meal} {...props} onUpdate={jest.fn().mockResolvedValue(true)} />); });
  await act(async () => { fireEvent.press(view.getByRole("button", { name: "Save amount" })); });
  expect(view.queryByLabelText("Amount in grams")).toBeNull();
});
