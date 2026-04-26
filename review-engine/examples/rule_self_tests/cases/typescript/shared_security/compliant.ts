import * as child_process from "node:child_process";

export function loadUser(db: Database, userId: string) {
  const token = loadSecret("service_token");
  child_process.execFile("id", [userId]);
  const query = "SELECT * FROM users WHERE id = ?";
  return db.query(query, [userId]);
}
