jest.mock("expo-file-system", () => ({
  File: jest.fn().mockImplementation((uri: string) => Object.assign(new Blob(), { uri })),
}));

import { File } from "expo-file-system";

import { getHealth, getMeal, uploadMealImage } from "../services/api";


test("health client returns the typed backend contract", async () => {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ status: "ok", mode: "live", providers: { vision: "openai", canonicalization: "openai", nutrition: "usda" } }),
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  await expect(getHealth()).resolves.toEqual({ status: "ok", mode: "live", providers: { vision: "openai", canonicalization: "openai", nutrition: "usda" } });
  expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/health$/));
});

test("stable USDA errors receive actionable client copy", async () => {
  globalThis.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 422,
    json: async () => ({ error: { code: "USDA_INCOMPLETE_NUTRITION" } }),
  }) as unknown as typeof fetch;

  await expect(getMeal("meal-123")).rejects.toEqual(
    expect.objectContaining({ code: "USDA_INCOMPLETE_NUTRITION", message: "That food lacks complete nutrition data. Choose another match." }),
  );
});

test("AI nutrition errors receive actionable client copy", async () => {
  globalThis.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 503,
    json: async () => ({ error: { code: "AI_NUTRITION_TIMEOUT" } }),
  }) as unknown as typeof fetch;

  await expect(getMeal("meal-123")).rejects.toEqual(
    expect.objectContaining({ code: "AI_NUTRITION_TIMEOUT", message: "Nutrition estimation took too long. Please try again." }),
  );
});

test("image upload appends an Expo File for standards-compliant multipart fetch", async () => {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({}),
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  await uploadMealImage("meal-123", {
    uri: "file:///cache/meal.jpeg",
    fileName: "meal.jpeg",
    mimeType: "image/jpeg",
  });

  expect(File).toHaveBeenCalledWith("file:///cache/meal.jpeg");
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringMatching(/\/api\/v1\/meals\/meal-123\/image$/),
    expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
  );
});
