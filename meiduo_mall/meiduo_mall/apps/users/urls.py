from django.conf.urls import url
from rest_framework import routers
from rest_framework.routers import DefaultRouter
from rest_framework_jwt.views import obtain_jwt_token

from . import views



urlpatterns=[

    url(r'^users/$',views.UserView.as_view()),
    url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view()),
    url(r'^mobiles/(?P<mobile>1[3-9]\d{9})/count/$',views.MobileCountView.as_view()),

    #url(r'^authorizations/$', obtain_jwt_token), #登录路由
    url(r'^authorizations/$', views.UserAuthorizeView.as_view()), #登录路由

    # 获取用户个信信息
    url(r'^user/$', views.UserDetailView.as_view()),

    url(r'^email/$', views.EmailView.as_view()),  # 设置邮箱

    url(r'^emails/verification/$', views.VerifyEmailView.as_view()),

    #浏览记录
    url(r'^browse_histories/$', views.UserBrowsingHistoryView.as_view()),

    #找回密码
    url(r'^accounts/(?P<username>\w{5,20})/sms/token/$',views.AccountsUserView.as_view()),

    #找回密码
    url(r'^accounts/(?P<username>\w{5,20})/password/token/$',views.AccountsPassowordView.as_view()),

    #/users/user_id/password/
    url(r'^users/(?P<user_id>\d{1,11})/password/$',views.UndefinedPassowordView.as_view())
]


router = routers.DefaultRouter()
router.register(r'addresses', views.AddressViewSet, base_name='addresses')

urlpatterns += router.urls

# POST /addresses/ 新建  -> create
# PUT /addresses/<pk>/ 修改  -> update
# GET /addresses/  查询  -> list
# DELETE /addresses/<pk>/  删除 -> destroy
# PUT /addresses/<pk>/status/ 设置默认 -> status
# PUT /addresses/<pk>/title/  设置标题 -> title