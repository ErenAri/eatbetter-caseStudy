import { fireEvent, render } from "@testing-library/react-native";
import { AnalysisScreen } from "../features/meal-capture/AnalysisScreen";
import { CaptureScreen } from "../features/meal-capture/CaptureScreen";

test("capture requires an image and keeps context optional", async () => {
  const view = await render(<CaptureScreen image={null} context="" busy={false} error={null} demoAvailable={false} onImage={jest.fn()} onContext={jest.fn()} onAnalyze={jest.fn()} onDemo={jest.fn()} onBack={jest.fn()} />);
  expect(view.getByRole("button", { name: "Take Photo" })).toBeTruthy();
  expect(view.getByText(/Add context/)).toBeTruthy();
  expect(view.getByRole("button", { name: "Analyze meal" }).props.accessibilityState.disabled).toBe(true);
});

test("analysis error retains photo recovery actions", async () => {
  const retry = jest.fn();
  const view = await render(<AnalysisScreen error="Meal analysis is temporarily unavailable." onRetry={retry} onChooseAnother={jest.fn()} onCancel={jest.fn()} />);
  expect(view.getByText("Your photo is still available.")).toBeTruthy();
  fireEvent.press(view.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledTimes(1);
});
