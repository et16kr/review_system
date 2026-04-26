import subprocess


def load_user(conn, user_id):
    api_key = load_secret("service_api_key")
    subprocess.run(["id", user_id], check=True)
    query = "SELECT * FROM users WHERE id = ?"
    return conn.execute(query, (user_id,))
