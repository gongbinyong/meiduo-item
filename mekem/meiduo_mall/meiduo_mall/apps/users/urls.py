from django.conf.urls import url
from rest_framework_jwt.views import obtain_jwt_token
from rest_framework.routers import DefaultRouter

from . import views

urlpatterns = [
    # 注册用户
    url(r'^users/$', views.UserView.as_view()),

    # 判断用户名是否已存在
    url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view()),

    # 判断手机号是否已存在
    url(r'^mobiles/(?P<mobile>1[3-9]\d{9})/count/$', views.MobileCountView.as_view()),

    # JWT登陆
    url(r'^authorizations/$', obtain_jwt_token),

    # 获取用户个人详细信息
    url(r'^user/$', views.UserDetailView.as_view()),

    # 保存邮箱
    url(r'^email/$', views.EmailView.as_view()),

    # 激活邮箱
    url(r'^emails/verification/$', views.EmailVerifyView.as_view()),

    # 浏览记录
    url(r'^browse_histories/$', views.UserBrowseHistoryView.as_view()),

    # 忘记密码（获取图片验证码）
    # url(r'^image_codes/(?P<uuid>.*)/$',views.ImageVerificationCode.as_view()),
    url(r'^image_codes/(?P<image_code_id>\w{8}(-\w{4}){3}-\w{12})/$', views.ImageCaptchaView.as_view()),

    # 忘记密码（第一步提交表单-->账号和图片验证码检验）
    url(r'^accounts/(?P<username>.*)/sms/token/$',views.AccountImageCodeCheckView.as_view()),

    # 忘记密码（获取短信验证码）
    url(r'^sms_codes/$', views.ForgetPasswordSMSCodeView.as_view()),

    # 忘记密码（第二步提交表单-->验证手机号和短信验证码）
    url(r'^accounts/(?P<username>.*)/password/token/$',views.MobileSmsCodeView.as_view()),

    # 忘记密码（第三步提交表单-->验证token ,验证提交修改密码数据）
    url(r'^users/(?P<user_id>.*)/password/$',views.ModifyPasswordView.as_view()),
]

router = DefaultRouter()
router.register(r'addresses', views.AddressViewSet, base_name='addresses')
urlpatterns += router.urls
