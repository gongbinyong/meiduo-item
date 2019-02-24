from django_redis import get_redis_connection
from rest_framework import serializers
from users.models import User
from .utils import check_save_user_token
from .models import OAuthQQUser


class QQAuthUserSerializer(serializers.Serializer):
    access_token = serializers.CharField(label='操作凭证')
    mobile = serializers.RegexField(label='手机号', regex=r'^1[3-9]\d{9}$')
    password = serializers.CharField(label='密码', max_length=20, min_length=8)
    sms_code = serializers.CharField(label='短信验证码')

    def validate(self, attrs):
        access_token = attrs.get("access_token")
        openid = check_save_user_token(access_token)
        if not openid:
            raise serializers.ValidationError('openid无效')
        attrs['access_token'] = openid
        redis_conn = get_redis_connection('verify_codes')
        mobile = attrs.get("mobile")
        real_sms_code = redis_conn.get(mobile)
        if real_sms_code is None:
            raise serializers.ValidationError('无效的短信验证码')
        if attrs.get('sms_code') != real_sms_code.decode():
            raise serializers.ValidationError('短信验证码错误')
        qs = User.objects.filter(mobile=mobile)
        count = qs.count()
        if count > 0:
            user = qs.first()
            if not user.check_password(attrs.get('password')):
                raise serializers.ValidationError('用户已存在,但密码不正确')
            else:
                attrs['user'] = user
        return attrs

    def create(self, validated_data):
        user = validated_data.get('user')
        if not user:  # 如果用户是不存在的,那就新增一个用户
            user = User(
                username=validated_data.get('mobile'),
                password=validated_data.get('password'),
                mobile=validated_data.get('mobile')
            )
            user.set_password(validated_data.get('password'))  # 对密码进行加密
            user.save()

        # 让user和openid绑定
        OAuthQQUser.objects.create(
            user=user,
            openid=validated_data.get('access_token')
        )

        return user
