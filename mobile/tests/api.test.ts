import { getHealth } from "../services/api";


test("health client returns the typed backend contract", async () => {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ status: "ok" }),
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  await expect(getHealth()).resolves.toEqual({ status: "ok" });
  expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/health$/));
});
