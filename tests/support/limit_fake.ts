// The Workers rate limit binding: `limit` succeeds until a key has made `max` calls. The default lets every call in.
export function fakeLimit(max = Infinity) {
  const used = new Map<string, number>();
  return {
    limit: async ({ key }: { key: string }) => {
      const n = used.get(key) ?? 0;
      if (n >= max) return { success: false };
      used.set(key, n + 1);
      return { success: true };
    },
  };
}
