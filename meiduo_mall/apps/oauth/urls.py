from django.conf.urls import url
from . import views

urlpatterns=[
    url(r'^qq/authorization/$',view=views.QQAuthURLView.as_view()),
    url(r'^qq/user/$',view=views.QQAuthUserView.as_view())
]