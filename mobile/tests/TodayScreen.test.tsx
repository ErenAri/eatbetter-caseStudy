import { fireEvent, render } from "@testing-library/react-native";
import { TodayScreen } from "../features/meal-history/TodayScreen";
import { baseMeal, reviewMeal } from "./fixtures";

const totals = { calories_kcal: 264, protein_g: 49.6, carbs_g: 0, fat_g: 5.8 };
test("shows concise empty state", async () => {
  const onLog = jest.fn();
  const view = await render(<TodayScreen meals={[]} totals={{ calories_kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 }} loading={false} onLog={onLog} onOpen={jest.fn()} />);
  expect(view.getByText("No meals logged yet")).toBeTruthy();
  fireEvent.press(view.getByRole("button", { name: "Log your first meal" }));
  expect(onLog).toHaveBeenCalledTimes(1);
});

test("shows confirmed meal nutrition and pending meals", async () => {
  const pending = { ...reviewMeal(), id: "pending" };
  const view = await render(<TodayScreen meals={[baseMeal, pending]} totals={totals} loading={false} onLog={jest.fn()} onOpen={jest.fn()} />);
  expect(view.getAllByText("264 kcal").length).toBeGreaterThan(0);
  expect(view.getByText("Needs review")).toBeTruthy();
  expect(view.getByText(/quick checks remaining/)).toBeTruthy();
});
