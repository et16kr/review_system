def view(User):
    return User.objects.raw(query)
