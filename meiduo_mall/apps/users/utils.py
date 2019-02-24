import re
from .models import User
from django.contrib.auth.backends import ModelBackend


def jwt_response_payload_handler(token, user=None, request=None):
    # 重写JWT登录认证方法的响应体
    return {
        'token': token,
        'user_id': user.id,
        'username': user.username
    }

def get_user_by_account(account):
    """根据传⼊入的账号获取⽤用户信息"""
    try:
        if re.match('^1[3-9]\d{9}$', account):
        # ⼿手机号登录
            user = User.objects.get(mobile=account)
        else:
            # ⽤用户名登录
            user = User.objects.get(username=account)
    except User.DoesNotExist:
        return None
    else:
        return user


class UsernameMobileAuthBackend(ModelBackend):
    # 重写认证方法，实现多帐号登录
    def authenticate(self, request, username=None, password=None, **kwargs):
        # 根据传⼊入的username获取user对象。username可以是⼿手机号也可以是账号
        user = get_user_by_account(username)
        # 校验user是否存在并校验密码是否正确
        if user and user.check_password(password):
            return user
