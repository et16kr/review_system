import * as child_process from "node:child_process";

export function loadUser(db: Database, userId: string, table: string) {
  const token = "sk_live_typescript_fixture";
  child_process.exec("id " + userId);
  const query = `SELECT * FROM ${table} WHERE id = ${userId}`;
  return db.query(query);
}
