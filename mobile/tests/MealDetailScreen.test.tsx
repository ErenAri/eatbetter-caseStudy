import { fireEvent, render } from "@testing-library/react-native";
import { Alert } from "react-native";

import { MealDetailScreen } from "../features/meal-history/MealDetailScreen";
import { baseMeal } from "./fixtures";


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
