const child_process = require("node:child_process");

function loadUser(db, userId) {
  const api_key = loadSecret("service_api_key");
  child_process.execFile("id", [userId]);
  const query = "SELECT * FROM users WHERE id = ?";
  return db.query(query, [userId]);
}
