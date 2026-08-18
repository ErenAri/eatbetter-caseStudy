import { fireEvent, render } from "@testing-library/react-native";
import { ReviewScreen } from "../features/meal-review/ReviewScreen";
import { baseMeal, canonicalClarification, hiddenClarification, portionClarification, reviewMeal } from "./fixtures";

const props = { busyKey: null, error: null, onAnswer: jest.fn(), onUpdate: jest.fn(), onRemove: jest.fn(), onAdd: jest.fn(), onConfirm: jest.fn(), onBack: jest.fn() };
test("resolved item shows Looks good and enables save", async () => {
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const view = await render(<ReviewScreen meal={meal} {...props} />);
  expect(view.getByText("✓ Looks good")).toBeTruthy();
  expect(view.getByRole("button", { name: "Save meal" }).props.accessibilityState.disabled).toBe(false);
});

test("portion clarification submits the stored option and disables save", async () => {
  const onAnswer = jest.fn();
  const view = await render(<ReviewScreen meal={reviewMeal(portionClarification)} {...props} onAnswer={onAnswer} />);
  expect(view.getByText("How much rice was there?")).toBeTruthy();
  fireEvent.press(view.getByRole("button", { name: "About this amount" }));
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

test("hidden ingredient clarification uses simple product language", async () => {
  const view = await render(<ReviewScreen meal={reviewMeal(hiddenClarification)} {...props} />);
  expect(view.getByText("Was cooking oil used?")).toBeTruthy();
  expect(view.getByText(/significantly change/)).toBeTruthy();
  expect(view.getByRole("button", { name: "Not sure" })).toBeTruthy();
});

test("remove food delegates the item action", async () => {
  const onRemove = jest.fn();
  const meal = { ...baseMeal, status: "NEEDS_REVIEW" as const, confirmed_at: null };
  const view = await render(<ReviewScreen meal={meal} {...props} onRemove={onRemove} />);
  fireEvent.press(view.getByRole("button", { name: "Remove" }));
  expect(onRemove).toHaveBeenCalledWith(meal.items[0]);
});
