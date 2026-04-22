import yaml


def load_user(payload, user_id):
    assert user_id
    return yaml.load(payload, Loader=yaml.Loader)
