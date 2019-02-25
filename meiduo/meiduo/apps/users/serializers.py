import re

from django_redis import get_redis_connection
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework_jwt.settings import api_settings

from goods.models import SKU
from users.models import User, Address
from celery_tasks.email.tasks import send_verify_email


class UserSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(label='确认密码', write_only=True)
    sms_code = serializers.CharField(label='短信验证码', write_only=True)
    allow = serializers.CharField(label='同意协议', write_only=True)
    token = serializers.CharField(label='登录状态', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'password2', 'mobile', 'sms_code', 'allow', 'token']

        extra_kwargs = {
            'username': {
                'min_length': 5,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许5-20个字符的用户名',
                    'max_length': '仅允许5-20个字符的用户名',
                }
            },
            'password': {
                'write_only': True,
                'min_length': 8,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许8-20个字符的密码',
                    'max_length': '仅允许8-20个字符的密码',
                }
            }
        }

    def validated_mobile(self, mobile):
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            raise serializers.ValidationError('手机号格式错误')
        return mobile

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError('两次密码不一致')
        redis_conn = get_redis_connection('verify_codes')
        mobile = data['mobile']
        real_sms_code = redis_conn.get(mobile)
        if real_sms_code is None:
            raise serializers.ValidationError('无效的短信验证码')
        if data['sms_code'] != real_sms_code.decode():
            raise serializers.ValidationError('短信验证码错误')
        return data

    def validate_allow(self, allow):
        if allow != 'true':
            raise serializers.ValidationError('请同意用户协议')
        return allow

    def create(self, validated_data):
        del validated_data['password2']
        del validated_data['sms_code']
        del validated_data['allow']
        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.save()
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)
        user.token = token

        return user


class UpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(label='旧密码', write_only=True, required=True)
    password = serializers.CharField(label='新密码', min_length=8, max_length=20, write_only=True, required=True)
    password2 = serializers.CharField(label='确认密码', write_only=True, required=True)

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError('两次密码不一致')
        return data


class UserDetailSerializer(serializers.ModelSerializer):
    """
    用户详细信息序列化器
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'mobile', 'email', 'email_active']


class EmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email']
        extra_kwargs = {
            'email': {
                'required': True
            }
        }

    def update(self, instance, validated_data):
        instance.email = validated_data['email']
        instance.save()
        verify_url = instance.generate_verify_email_url()
        send_verify_email.delay(instance.email, verify_url)
        return instance


class UserAddressSerializer(serializers.ModelSerializer):
    """
    用户地址序列化器
    """
    province = serializers.StringRelatedField(read_only=True)
    city = serializers.StringRelatedField(read_only=True)
    district = serializers.StringRelatedField(read_only=True)
    province_id = serializers.IntegerField(label='省ID', required=True)
    city_id = serializers.IntegerField(label='市ID', required=True)
    district_id = serializers.IntegerField(label='区ID', required=True)

    class Meta:
        model = Address
        exclude = ('user', 'is_deleted', 'create_time', 'update_time')

    def validate_mobile(self, value):
        """
        验证手机号
        """
        if not re.match(r'^1[3-9]\d{9}$', value):
            raise serializers.ValidationError('手机号格式错误')
        return value

    def create(self, validated_data):
        user = self.context['request'].user  # 获取到用户对象
        validated_data['user'] = user
        address = Address.objects.create(**validated_data)
        return address


class AddressTitleSerializer(serializers.ModelSerializer):
    """
    地址标题
    """

    class Meta:
        model = Address
        fields = ('title',)


class UserBrowseHistorySerializer(serializers.Serializer):
    """浏览记录"""

    sku_id = serializers.IntegerField(label='商品id', min_value=1)

    def validate_sku_id(self, value):
        """
        对sku_id追加额外校验逻辑
        :param value: sku_id
        :return: value
        """
        try:
            SKU.objects.get(id=value)
        except SKU.DoesNotExist:
            raise serializers.ValidationError('sku_id不存在')

        return value

    def create(self, validated_data):
        """重写此方法把sku_id存储到redis    validated_data: {'sku_id: 1}"""

        # 创建redis连接对象
        redis_conn = get_redis_connection('history')
        # 获取user_id
        user_id = self.context['request'].user.id
        # 获取sku_id
        sku_id = validated_data.get('sku_id')
        # 创建管道对象
        pl = redis_conn.pipeline()

        # 先去重
        # redis_conn.lrem(key, count, value)
        pl.lrem('history_%d' % user_id, 0, sku_id)
        # 存储到列表的最前面
        pl.lpush('history_%d' % user_id, sku_id)
        # 截取前5个
        pl.ltrim('history_%d' % user_id, 0, 4)
        # 执行管道
        pl.execute()

        # 返回
        return validated_data


class ImageCodeSerilizer(serializers.ModelSerializer):
    """图片验证码"""
    token = serializers.CharField(label='非登录状态token', read_only=True)
    mobile = serializers.IntegerField(label='手机号', read_only=True, min_value=11)

    class Meta:
        model = User
        fields = ['token', 'mobile']

    @staticmethod
    def validate_account(self, account):
        try:
            if re.match('^1[3-9]\d{9}$', account):
                # ⼿机号登录
                user = User.objects.get(mobile=account)
            else:
                # ⽤户名登录
                user = User.objects.get(username=account)
        except User.DoesNotExist:
            return None

        # 通过验证的username账户执行以下操作

        # 查找该用户的手机号
        mobile = user.mobile

        # 手动生成token

        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数

        payload = jwt_payload_handler(user)  # 生成载荷
        # user是一个用户对象，未登录不应该把所有信息放载荷，会泄露信息
        del payload['email']
        del payload['user_id']
        # print(payload)
        token = jwt_encode_handler(payload)  # 根据载荷生成token

        return mobile, token

    @staticmethod
    def validate_image_code(self, text, image_code_id):
        # 校验用户输入的图片验证码
        try:
            redis_conn = get_redis_connection('verify_image_codes')
            real_image_code = redis_conn.get('ImageCodeId_%s' % image_code_id)
        except Exception:
            raise Exception('验证码过期')
        else:
            if real_image_code == None:
                raise serializers.ValidationError('图片验证码未生成')
            elif text != real_image_code.decode().lower():
                raise serializers.ValidationError('图片验证码不正确')
            return


class SmsCodeSerilizer(serializers.ModelSerializer):
    @staticmethod
    def token_decode(self, token):
        # 手动解开生成token

        jwt_payload_get_username_handler = api_settings.JWT_PAYLOAD_GET_USERNAME_HANDLER  # 加载载荷生成username函数
        jwt_decode_handler = api_settings.JWT_DECODE_HANDLER  # 加载生成token函数
        payload = jwt_decode_handler(token)  # 根据token载荷解密得到payload
        username = jwt_payload_get_username_handler(payload)  #
        return username


class PasswordModifySerilizer(serializers.ModelSerializer):
    """修改密码"""

    password2 = serializers.CharField(label='确认密码', write_only=True)
    access_token = serializers.CharField(label='登录状态token',read_only=True)

    class Meta:
        model = User
        fields = ['id', 'password', 'password2','access_token']
        extra_kwargs = {
            'password': {
                'write_only': True,
                'min_length': 8,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许8～20个字符的密码',
                    'max_length': '仅允许8～20个字符的密码',
                }
            }
        }

    def validate_access_token(self,data):
        # 手动解开生成token
        jwt_payload_get_username_handler = api_settings.JWT_PAYLOAD_GET_USERNAME_HANDLER  # 加载载荷生成username函数
        jwt_decode_handler = api_settings.JWT_DECODE_HANDLER  # 加载生成token函数
        payload = jwt_decode_handler(data)  # 根据token载荷解密得到payload
        user = jwt_payload_get_username_handler(payload)  #
        return user

    def validate(self,data):
        # 判断两次密码
        if data['password'] != data['password2']:
            raise serializers.ValidationError('两次密码不⼀致')
        return data

    def update(self, instance, validated_data):
        """重写create方法"""
        # validated_data的字段:'username', 'password', 'password2', 'mobile', 'sms_code', 'allow'
        # 真正需要存储到mysql中的字段:username password mobile
        del validated_data['password2']
        instance.set_password(validated_data['password'])
        instance.save()
        print(instance.username)
        # 手动生成token
        user=User.objects.get(username=instance.username)
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
        payload = jwt_payload_handler(user)  # 生成载荷
        token = jwt_encode_handler(payload)  # 根据载荷生成token
        # 给user多添加一个属性
        user.token = token
        return user
