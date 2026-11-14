// Imported first by every test file: any accidental use of the real global fetch fails loudly instead of
// reaching the network. All tests must inject `fetchImpl`.
globalThis.fetch = async (url) => {
  throw new Error(`Real network access is forbidden in tests (attempted ${url}). Inject fetchImpl.`);
};
