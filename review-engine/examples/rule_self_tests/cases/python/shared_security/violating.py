import subprocess


def load_user(conn, user_id, table):
    api_key = "sk_live_python_fixture"
    command = "id " + user_id
    subprocess.run(command, shell=True)
    query = f"SELECT * FROM {table} WHERE id = %s"
    return conn.execute(query, (user_id,))
