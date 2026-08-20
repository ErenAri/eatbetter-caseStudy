import { fireEvent, render } from "@testing-library/react-native";
import { Alert } from "react-native";

import { MealDetailScreen } from "../features/meal-history/MealDetailScreen";
import { baseMeal, readyItem } from "./fixtures";


test("discarding an incomplete meal requires destructive confirmation", async () => {
  const onDiscard = jest.fn();
  const alert = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
  const meal = {
    ...baseMeal,
    status: "UPLOADED" as const,
    confirmed_at: null,
    image_attached: true,
    items: [],
  };
  const view = await render(
    <MealDetailScreen
      meal={meal}
      busy={false}
      error={null}
      onDiscard={onDiscard}
      onBack={jest.fn()}
    />,
  );

  fireEvent.press(view.getByRole("button", { name: "Discard and start over" }));
  expect(onDiscard).not.toHaveBeenCalled();
  expect(alert).toHaveBeenCalledWith(
    "Discard this meal?",
    expect.stringContaining("permanently deletes"),
    expect.any(Array),
  );
  const buttons = alert.mock.calls[0]?.[2];
  buttons?.find((button) => button.text === "Discard")?.onPress?.();
  expect(onDiscard).toHaveBeenCalledTimes(1);
  alert.mockRestore();
});

test("an AI_ESTIMATE meal renders the AI label and never claims to be verified", async () => {
  const meal = {
    ...baseMeal,
    items: [{ ...readyItem, canonical: { source: "AI_ESTIMATE", food_id: "grilled chicken breast", name: "grilled chicken breast" } }],
  };
  const view = await render(
    <MealDetailScreen meal={meal} busy={false} error={null} onBack={jest.fn()} />,
  );

  expect(view.getByText("Nutrition data: AI estimate — not database-verified")).toBeTruthy();
  expect(view.queryByText("Nutrition data: verified sources")).toBeNull();
  expect(view.queryByText(/verified sources/i)).toBeNull();
});
