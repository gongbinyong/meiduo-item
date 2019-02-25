from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView, UpdateAPIView
from rest_framework.mixins import UpdateModelMixin, CreateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
# from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.views import ObtainJSONWebToken

from carts.utils import merge_cart_cookie_to_redis
from goods.models import SKU
from goods.serializers import SKUSerializer
from meiduo.utils.captcha.captcha import captcha
from verifications.views import SMSCodeView
from .models import User
from .serializers import UserSerializer, UserDetailSerializer, EmailSerializer, UserAddressSerializer, \
    AddressTitleSerializer, UserBrowseHistorySerializer, UpdatePasswordSerializer, SmsCodeSerilizer, ImageCodeSerilizer, \
    PasswordModifySerilizer


class UserView(CreateAPIView):
    serializer_class = UserSerializer


class UsernameCountView(APIView):
    def get(self, request, username):
        count = User.objects.filter(username=username).count()
        data = {
            'count': count,
            'username': username
        }
        return Response(data)


class MobileCountView(APIView):
    def get(self, request, mobile):
        count = User.objects.filter(mobile=mobile).count()
        data = {
            'count': count,
            'mobile': mobile
        }
        return Response(data)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserDetailSerializer(user)
        return Response(serializer.data)


class EmailView(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmailSerializer

    def get_object(self):
        return self.request.user


class EmailVerifyView(APIView):
    """激活邮箱"""
    def get(self, request):

        # 1.获取前token查询参数
        token = request.query_params.get('token')
        if not token:
            return Response({'message': '缺少token'}, status=status.HTTP_400_BAD_REQUEST)

        # 对token解密并返回查询到的user
        user = User.check_verify_email_token(token)

        if not user:
            return Response({'message': '无效token'}, status=status.HTTP_400_BAD_REQUEST)

        # 修改user的email_active字段
        user.email_active = True
        user.save()

        return Response({'message': 'ok'})


class AddressViewSet(UpdateModelMixin, CreateModelMixin, GenericViewSet):
    """用户收货地址"""
    permission_classes = [IsAuthenticated]

    serializer_class = UserAddressSerializer

    def create(self, request, *args, **kwargs):
        """新增收货地址"""
        # 判断用户的收货地址数量是否上限
        # address_count = Address.objects.filter(user=request.user).count()
        address_count = request.user.addresses.count()
        if address_count > 20:
            return Response({'message': '收货地址数量上限'}, status=status.HTTP_400_BAD_REQUEST)
        # # 创建序列化器给data参数传值(反序列化)
        #         # serializer = UserAddressSerializer(data=request.data, context={'request': request})
        #         # # 调用序列化器的is_valid方法
        #         # serializer.is_valid(raise_exception=True)
        #         # # 调用序列化器的save
        #         # serializer.save()
        #         # # 响应
        #         # return Response(serializer.data, status=status.HTTP_201_CREATED)
        return super(AddressViewSet, self).create(request, *args, **kwargs)

    def get_queryset(self):
        return self.request.user.addresses.filter(is_deleted=False)

    # GET /addresses/
    def list(self, request, *args, **kwargs):
        """
        用户地址列表数据
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        user = self.request.user
        return Response({
            'user_id': user.id,
            'default_address_id': user.default_address_id,
            'limit': 20,
            'addresses': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """
        处理删除
        """
        address = self.get_object()

        # 进行逻辑删除
        address.is_deleted = True
        address.save()

        return Response(status=status.HTTP_204_NO_CONTENT)



    # put /addresses/pk/status/
    @action(methods=['put'], detail=True)
    def status(self, request, pk=None):
        """
        设置默认地址
        """
        address = self.get_object()
        request.user.default_address = address
        request.user.save()
        return Response({'message': 'OK'}, status=status.HTTP_200_OK)

    # put /addresses/pk/title/
    # 需要请求体参数 title
    @action(methods=['put'], detail=True)
    def title(self, request, pk=None):
        """
        修改标题
        """
        address = self.get_object()
        serializer = AddressTitleSerializer(instance=address, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserBrowseHistoryView(CreateAPIView):
    """用户浏览记录"""

    # 指定序列化器(校验)
    serializer_class = UserBrowseHistorySerializer
    # 指定权限
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """读取用户浏览记录"""
        # 创建redis连接对象
        redis_conn = get_redis_connection('history')
        # 查询出redis中当前登录用户的浏览记录[b'1', b'2', b'3']
        sku_ids = redis_conn.lrange('history_%d' % request.user.id, 0, -1)

        # 把sku_id对应的sku模型取出来
        # skus = SKU.objects.filter(id__in=sku_ids)  # 此查询它会对数据进行排序处理
        # 查询sku列表数据
        sku_list = []
        for sku_id in sku_ids:
            sku = SKU.objects.get(id=sku_id)
            sku_list.append(sku)

        # 序列化器
        serializer = SKUSerializer(sku_list, many=True)

        return Response(serializer.data)


class UserAuthorizeView(ObtainJSONWebToken):
    """重写账号密码登录视图"""
    def post(self, request, *args, **kwargs):
        response = super(UserAuthorizeView, self).post(request, *args, **kwargs)
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            user = serializer.object.get('user') or request.user
            merge_cart_cookie_to_redis(request, user, response)

        return response


class UpdatePassowordView(APIView):
    """修改密码"""
    permission_classes = [IsAuthenticated]

    def put(self, request, user_id):
        user = request.user
        if not user.check_password(request.data.get('old_password')):
            return Response({'message': '当前密码错误'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = UpdatePasswordSerializer(user, request.data)
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["password"])
        user.save()
        return Response({"message": "OK"})


# Create your views here.
# 前段通过一个类似字典的json数据传送密码和access_token,需要解密
# POST /users/用户id/password/,
#           {password: this.password,password2: this.password2,access_token: this.access_token}
# post host/users/this.user_id/password/', {password: this.password,password2: this.password2,access_token: this.access_token}
class ModifyPasswordView(APIView):
    def post(self, request, user_id):
        user=User.objects.get(id=user_id)


        serilizer = PasswordModifySerilizer(instance=user,data=request.data)

        serilizer.is_valid(raise_exception=True)
        print(serilizer.validated_data)
        serilizer.save()

        data=serilizer.data

        return Response(data)


# GET /accounts/账户/password/token/?sms_code=xxxxxx
# 验证手机号和短信验证码,获取修改密码的access_token
class MobileSmsCodeView(APIView):
    def get(self, request, username):
        account = username
        user = User.objects.filter(Q(username=account) | Q(mobile=account)).first()
        if not user:
            return Response({'message', '账号未注册'}, status=status.HTTP_404_NOT_FOUND)
        mobile = user.mobile
        sms_code = request.query_params.get('sms_code')
        # print('1')
        redis_conn = get_redis_connection('verify_codes')
        # print('2')
        real_sms_code = redis_conn.get(mobile)
        # print('3')

        if int(sms_code) != int(real_sms_code.decode()):
            # print('4')
            print(type(sms_code), type(real_sms_code))
            return Response({'message': '验证码错误'}, status=status.HTTP_400_BAD_REQUEST)

        # this.user_id = response.data.user_id;
        # this.access_token = response.data.access_token;
        print('5')

        payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
        encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数

        payload = payload_handler(user)  # 生成载荷
        token = encode_handler(payload)  # 根据载荷生成token

        print('6')

        access_token = token
        data = {

            'access_token': access_token,
            'user_id': user.id,
        }
        print('7')
        return Response(data)


# 忘记密码的发送短信验证码视图
# GET /sms_codes/?access_token=xxx
class ForgetPasswordSMSCodeView(APIView):
    def get(self, request):
        try:
            access_token = request.query_params.get('access_token')
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if not access_token:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        username = SmsCodeSerilizer.token_decode(self, access_token)

        user = User.objects.get(username=username)
        mobile = user.mobile
        # print(mobile)
        SMSCodeView.get(self, request, mobile)
        return Response({'message': 'OK'})


# '/accounts/' + this.username + '/sms/token/?text='+ this.image_code + '&image_code_id=' + this.image_code_id
# GET /accounts/手机号/sms/token/?text=用户输入的图片验证码&image_code_id=后端生成的图片验证码的UUID
class AccountImageCodeCheckView(APIView):
    def get(self, request, username):
        """

        """
        text = request.query_params.get('text')
        image_code_id = request.query_params.get('image_code_id')
        # 使用 itsdangerous 生成凭据 access_token，使用 TimedJSONWebSignatureSerializer 可以生成带有有效期的 token。
        # JWT 和 itsdangerous 生成的token区别是，JWT 生成的 token 用来保持登录状态使用，而 其他需要验证的 token 都使用由 itsdangerous 生成的

        # 指定序列化机器
        serializer = ImageCodeSerilizer(data=request.query_params)

        # 检验账号,通过则　返回　查找该账号的手机号　和　生成的token

        result = ImageCodeSerilizer.validate_account(self, account=username)

        if result == None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        mobile, token = result

        # 校验图片验证码
        ImageCodeSerilizer.validate_image_code(self, text, image_code_id)

        # serializer.is_valid(raise_exception=True)  # 使用　.data和.validated_data　则必须调用.is_valid()方法！！！

        # 构造字典返回mobile;  access_token;

        data = {
            'mobile': mobile,
            'access_token': token,
        }

        return Response(data)


# GET /image_codes/6118056d-a342-4400-ae1a-818b268ac631/
class ImageCaptchaView(APIView):
    """
    1.获取参数
        1.1 获取image_code_id，全球唯一的编码（uuid）
    2.校验参数
        2.1 非空判断，判断image_code_id是否有值
    3.逻辑处理
        3.1 生成验证码图片 & 生成验证码图片的真实值（文字）
        3.2 以image_code_id作为key 将生成验证码图片的真实值（文字）存储到redis数据库
    4.返回值
        4.1 返回验证码图片,设置返回图片的格式
    """

    def get(self, request, image_code_id):
        # 1.1 获取全球唯一的编码（uuid)
        # 2.1 非空判断，判断uuid是否有值
        if not image_code_id:
            return Response({'message': '缺少image_code_id'}, status=status.HTTP_404_NOT_FOUND)

        # 3.1 生成验证码图片 & 生成验证码图片的真实值（文字）
        name, real_image_code, image = captcha.generate_captcha()
        # 3.2 以uuid作为key 将生成验证码图片的真实值（文字）存储到redis数据库
        IMAGE_CODE_REDIS_EXPIRES = 300  # 短信验证码的有效期
        redis_conn = get_redis_connection('verify_image_codes')
        redis_conn.setex('ImageCodeId_%s' % image_code_id, IMAGE_CODE_REDIS_EXPIRES, real_image_code)

        # 4.1 返回验证码图片,设置返回图片的格式
        return HttpResponse(image)