from rest_framework import serializers
from .utils import check_save_user_token
from django_redis import get_redis_connection
from users.models import User
from .models import QQAuthUser, OAuthSinaUser


class QQAuthUserSerializer(serializers.Serializer):

    """
        QQ登录创建用户序列化器
    """
    access_token = serializers.CharField(label='操作凭证')
    mobile = serializers.RegexField(label='手机号', regex=r'^1[3-9]\d{9}$')
    password = serializers.CharField(label='密码', max_length=20, min_length=8)
    sms_code = serializers.CharField(label='短信验证码')

    def validate(self,attrs):
        access_token = attrs.get('access_token')  #获取加密后的access_token
        openid = check_save_user_token(access_token)
        if not openid:
            raise serializers.ValidationError('openid无效')
        attrs['access_token']=openid
        #验证 短信验证码是否正确
        redis_coon = get_redis_connection('verify_codes')
        mobile = attrs.get('mobile')
        real_sms_code = redis_coon.get('sms_%s' %mobile)
        sms_code=attrs.get('sms_code')

        if sms_code != real_sms_code.decode():
            raise serializers.ValidationError('验证码错误')

        #判断手机号是新用户还是老用户
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            pass
        else:
            #此手机号已注册
            if user.check_password(attrs.get('password')):
                raise serializers.ValidationError('用户已存在，但密码错误')
            else:
                attrs['user']=user

        return attrs

    def create(self, validated_data):

        user = validated_data.get('user')

        if not user:
            user=User(
                username=validated_data.get('mobile'),
                password=validated_data.get('password'),
                mobile=validated_data.get('mobile')
            )
            user.set_password(validated_data.get('password'))
            user.save()
        QQAuthUser.objects.create(
            user=user,
            openid=validated_data.get('access_token'),
        )

        return user

class WBAuthUserSerializer(serializers.Serializer):

    """
        微博登录创建用户序列化器
    """
    access_token = serializers.CharField(label='操作凭证')
    mobile = serializers.RegexField(label='手机号', regex=r'^1[3-9]\d{9}$')
    password = serializers.CharField(label='密码', max_length=20, min_length=8)
    sms_code = serializers.CharField(label='短信验证码')

    def validate(self, attrs):
        access_token = attrs.get('access_token')  # 获取加密后的access_token
        access_token = check_save_user_token(access_token)
        if not access_token:
            raise serializers.ValidationError('openid无效')
        attrs['access_token'] = access_token

        # 验证 短信验证码是否正确
        redis_coon = get_redis_connection('verify_codes')
        mobile = attrs.get('mobile')
        real_sms_code = redis_coon.get('sms_%s' % mobile)

        sms_code = attrs.get('sms_code')

        if sms_code != real_sms_code.decode():
            raise serializers.ValidationError('验证码错误')

        # 判断手机号是新用户还是老用户
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            pass
        else:
            # 此手机号已注册
            if user.check_password(attrs.get('password')):
                raise serializers.ValidationError('用户已存在，但密码错误')
            else:
                attrs['user'] = user

        return attrs

    def create(self, validated_data):

        user = validated_data.get('user')

        if not user:
            user = User(
                username=validated_data.get('mobile'),
                password=validated_data.get('password'),
                mobile=validated_data.get('mobile')
            )
            user.set_password(validated_data.get('password'))
            user.save()
        OAuthSinaUser.objects.create(
            user=user,
            access_token=validated_data.get('access_token'),
        )

        return user