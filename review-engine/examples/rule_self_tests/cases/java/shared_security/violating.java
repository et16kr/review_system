class SecurityReview {
  private static final String apiKey = "sk_live_java_fixture";

  void loadUser(Connection conn, String userId, String table) throws Exception {
    Runtime.getRuntime().exec("id " + userId);
    String query = "SELECT * FROM " + table + " WHERE id = " + userId;
    conn.createStatement().executeQuery(query);
  }
}
