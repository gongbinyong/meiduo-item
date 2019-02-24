import re
from rest_framework import serializers
from django_redis import get_redis_connection
from rest_framework_jwt.settings import api_settings

from celery_tasks.email.tasks import send_verify_email
from .models import User, Address
from goods.models import SKU


class UserBrowseHistorySerializer(serializers.Serializer):
    """浏览记录"""

    sku_id = serializers.IntegerField(label='商品id', min_value=1)

    def validate_sku_id(self, value):
        """
        对sku_id追加额外的校验逻辑
        :param value: 传入的值sku_id
        :return: value: 校验后的值sku_id
        """
        try:
            SKU.objects.get(id=value)
        except SKU.DoesNotExist:
            raise serializers.ValidationError('sku_id不存在')

        return value

    def create(self, validated_data):
        """重写此方法把sku_id存储到redis  validated_data:{'sku_id':1} """

        # 创建redis连接对象
        redis_conn = get_redis_connection('history')

        # 获取user_id
        # 我的想法（未验证）
        # sku_id = validated_data['sku_id']
        # user_id = User.objects.get(id=sku_id)
        user_id = self.context['request'].user.id

        # 获取sku_id
        sku_id = validated_data.get('sku_id')

        # 创建管道对象
        pl = redis_conn.pipeline()

        # ---先去重 LREM (key,count,value) ---
        # count=0 从头找,0代表所有去重
        # count>0 从头找,count代表要去除重复个数
        # count<0 从尾找,count是负数它的绝对值代表要去除重复个数
        # redis_conn.lrem(key,count,value)
        pl.lrem('history_%d' % user_id, 0, sku_id)

        # ---存储到列表的最前面 LPUSH(key,value) or LPUSH(key,[value1,value2,....])---
        pl.lpush('history_%d' % user_id, sku_id)

        # ---截取前5个 LTRIM(key,start,stop) ---
        pl.ltrim('history_%d' % user_id, 0, 4)  # 从索引０到４，共截取５个

        # 执行管道
        pl.execute()

        # 返回
        return validated_data


class AddressTitleSerializer(serializers.ModelSerializer):
    """
    地址标题
    """

    class Meta:
        model = Address
        fields = ('title',)


class UserAddressSerializer(serializers.ModelSerializer):
    """
    ⽤户地址序列化器
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
        验证⼿机号
        """
        if not re.match(r'^1[3-9]\d{9}$', value):
            raise serializers.ValidationError('⼿机号格式错误')
        return value

    def create(self, validated_data):
        user = self.context['request'].user  # 获取到用户对象
        validated_data['user'] = user
        address = Address.objects.create(**validated_data)
        return address


class EmailSerializer(serializers.ModelSerializer):
    """邮箱序列化器"""

    class Meta:
        model = User
        fields = ['email', 'id']
        extra_kwargs = {
            'email': {
                'required': True
            }
        }

    # 用validated_data的数据去改instance模型的字段的值
    def update(self, instance, validated_data):
        instance.email = validated_data['email']
        instance.save()

        # 生成邮箱激活url
        # verify_url='www.meiduo.site:8080/success_verify_email.html?token=?'
        verify_url = instance.generate_verify_email_url()

        # 在此地发送邮件
        send_verify_email.delay(instance.email, verify_url)
        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    """用户个人信息"""

    class Meta:
        model = User
        fields = ['id', 'username', 'mobile', 'email', 'email_active']


class UserSerializer(serializers.ModelSerializer):
    """用户注册"""

    password2 = serializers.CharField(label='确认密码', write_only=True)
    sms_code = serializers.CharField(label='短信验证码', write_only=True)
    allow = serializers.CharField(label='同意协议', write_only=True)
    token = serializers.CharField(label='登录状态token', read_only=True)

    class Meta:
        model = User
        # 将来序列化器中需要的所有字段：'id','username','password','password2','mobile','sms_code','allow'
        # 模型中已存在的字段：'id','username','password','mobile'
        # 默认序列化   输出：'id','username','mobile'
        # 默认反序列化 输入：'username','password','password2','mobile','sms_code','allow'
        fields = ['id', 'username', 'password', 'password2', 'mobile', 'sms_code', 'allow', 'token']
        extra_kwargs = {
            'username': {
                'min_length': 5,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许５～２０个字符的用户名',
                    'max_length': '仅允许５～２０个字符的用户名',
                }
            },
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

    def validate_mobile(self, value):
        """验证⼿机号"""
        if not re.match(r'^1[3-9]\d{9}$', value):
            raise serializers.ValidationError('⼿机号格式错误')
        return value

    def validate_allow(self, value):
        """检验⽤户是否同意协议"""
        if value != 'true':
            raise serializers.ValidationError('请同意⽤户协议')
        return value

    def validate(self, data):
        # 判断两次密码
        if data['password'] != data['password2']:
            raise serializers.ValidationError('两次密码不⼀致')
        # 判断短信验证码
        redis_conn = get_redis_connection('verify_codes')
        mobile = data['mobile']
        real_sms_code = redis_conn.get('sms_%s' % mobile)
        if real_sms_code is None:
            raise serializers.ValidationError('⽆效的短信验证码')
        if data['sms_code'] != real_sms_code.decode():
            raise serializers.ValidationError('短信验证码错误')
        return data

    def create(self, validated_data):
        """重写create方法"""
        # validated_data的字段:'username', 'password', 'password2', 'mobile', 'sms_code', 'allow'
        # 真正需要存储到mysql中的字段:username password mobile
        del validated_data['password2']
        del validated_data['sms_code']
        del validated_data['allow']
        user = User(**validated_data)
        user.set_password(validated_data['password'])  # 对密码进行加密
        user.save()

        # 手动生成token

        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数

        payload = jwt_payload_handler(user)  # 生成载荷
        token = jwt_encode_handler(payload)  # 根据载荷生成token

        # 给user多添加一个属性
        user.token = token

        return user


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

            #         } else if (error.response.status == 404) {
            #         this.error_username_message = '用户名或手机号不存在';
            #         this.error_username = true;
            #     } else {
            #     console.log(error.response.data);
            #
            # }

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
        # print('1')
        payload = jwt_decode_handler(token)  # 根据token载荷解密得到payload
        # print('2')
        username = jwt_payload_get_username_handler(payload)  #
        # print('3')
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
        # print('1')
        del validated_data['password2']
        # print('2')
        # print(instance)
        instance.set_password(validated_data['password'])
        instance.save()

        print(instance.username)
        # 手动生成token
        user=User.objects.get(username=instance.username)
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数

        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
        print('1')
        payload = jwt_payload_handler(user)  # 生成载荷
        print('2')
        token = jwt_encode_handler(payload)  # 根据载荷生成token

        # 给user多添加一个属性
        user.token = token

        return user
