type User = {
  id: string;
};

const schema = {
  parse(raw: unknown): User {
    if (typeof raw === "object" && raw !== null && "id" in raw) {
      return { id: String((raw as { id: string }).id) };
    }
    throw new Error("invalid user");
  },
};

export function parseUser(payload: string): User {
  const raw: unknown = { id: payload };
  return schema.parse(raw);
}
