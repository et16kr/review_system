const child_process = require("node:child_process");

function loadUser(db, userId, table) {
  const api_key = "sk_live_javascript_fixture";
  child_process.exec("id " + userId);
  const query = "SELECT * FROM " + table + " WHERE id = " + userId;
  return db.query(query);
}
