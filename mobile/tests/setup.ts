// React Native Testing Library v14 performs asynchronous renderer setup.
jest.setTimeout(15000);
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("expo-file-system", () => {
  const contents = new Map<string, string>();
  const File = jest.fn().mockImplementation((...parts: Array<string | { uri?: string }>) => {
    const uri = parts.map((part) => typeof part === "string" ? part : part.uri ?? "").join("");
    return {
      uri,
      get exists() { return contents.has(uri); },
      create: () => { if (!contents.has(uri)) contents.set(uri, ""); },
      write: (value: string) => { contents.set(uri, value); },
      text: async () => contents.get(uri) ?? "",
      delete: () => { contents.delete(uri); },
    };
  });
  return { File, Paths: { document: { uri: "file:///document/" } } };
});
