from django.views.decorators.csrf import csrf_exempt
from django.utils.html import mark_safe

DEBUG = True


@csrf_exempt
def webhook(request):
    html = mark_safe(request.GET["banner"])
    User.objects.raw("select * from app_user")
    return html
