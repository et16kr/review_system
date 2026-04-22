type User = {
  id: string;
};

export function parseUser(payload: unknown): User {
  // @ts-expect-error bridging an unsafe boundary for now
  return payload as unknown as User;
}
