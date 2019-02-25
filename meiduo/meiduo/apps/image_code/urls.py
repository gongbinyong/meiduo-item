from django.conf.urls import url
from . import views

urlpatterns=[
    url(r'^image_codes/(?P<image>.*)/$',view=views.ImageCodes.as_view()),
]