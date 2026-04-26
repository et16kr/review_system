class SecurityReview {
  private static final String apiKey = loadSecret("service_api_key");

  void loadUser(Connection conn, String userId) throws Exception {
    new ProcessBuilder("id", userId).start();
    String query = "SELECT * FROM users WHERE id = ?";
    PreparedStatement statement = conn.prepareStatement(query);
    statement.setString(1, userId);
    statement.executeQuery();
  }
}
