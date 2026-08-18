jest.mock("expo-file-system", () => ({
  File: jest.fn().mockImplementation((uri: string) => Object.assign(new Blob(), { uri })),
}));

import { File } from "expo-file-system";

import { getHealth, uploadMealImage } from "../services/api";


test("health client returns the typed backend contract", async () => {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ status: "ok" }),
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  await expect(getHealth()).resolves.toEqual({ status: "ok" });
  expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/health$/));
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
