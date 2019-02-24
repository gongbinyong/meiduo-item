import logging

from QQLoginTool.QQtool import OAuthQQ
from django.conf import settings
from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.response import Response

from rest_framework.views import APIView
from rest_framework_jwt.settings import api_settings

from carts.utils import merge_cart_cookie_to_redis
from meiduo.utils.weibo import OAuth_WEIBO
from .serializers import QQAuthUserSerializer, WBAuthUserSerializer
from .models import OAuthQQUser, OAuthSinaUser
from .utils import generate_save_user_token

logger = logging.getLogger("django")


class QQAuthURLView(APIView):
    def get(self, request):
        next = request.query_params.get("next")
        if not next:
            next = '/'
            # 2.创建QQ登录sdk 的对象
        oauthqq = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                          client_secret=settings.QQ_CLIENT_SECRET,
                          redirect_uri=settings.QQ_REDIRECT_URI,
                          state=next)
        # 3.调用它里面的get_qq_url方法来拿到拼接好的扫码链接
        login_url = oauthqq.get_qq_url()

        # 4.把扫码url响应给前端
        return Response({'login_url': login_url})


class QQAuthUserView(APIView):
    def get(self, request):
        code = request.query_params.get("code")
        if not code:
            return Response({'message': '缺少code'}, status=status.HTTP_400_BAD_REQUEST)
        oauthqq = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                          client_secret=settings.QQ_CLIENT_SECRET,
                          redirect_uri=settings.QQ_REDIRECT_URI,
                          )
        try:
            access_token = oauthqq.get_access_token(code)
            openid = oauthqq.get_open_id(access_token)
        except Exception as error:
            logger.info(error)
            return Response({'message': 'QQ服务器异常'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            qquser = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            openid_secret = generate_save_user_token(openid)
            return Response({"access_token": openid_secret})
        else:
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
            # 获取user对象
            user = qquser.user
            payload = jwt_payload_handler(user)  # 生成载荷
            token = jwt_encode_handler(payload)  # 根据载荷生成token
            response = Response({
                'token': token,
                'username': user.username,
                'user_id': user.id
            })
            merge_cart_cookie_to_redis(request, user, response)
            return response

    def post(self, request):

        # 创建序列化器对象,进行反序列化
        serializer = QQAuthUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # 手动生成jwt Token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
        # 获取user对象

        payload = jwt_payload_handler(user)  # 生成载荷
        token = jwt_encode_handler(payload)  # 根据载荷生成token
        response = Response({
            'token': token,
            'username': user.username,
            'user_id': user.id
        })
        merge_cart_cookie_to_redis(request, user, response)
        return response


class WBAuthUserView(APIView):
    """扫码成功后的回调处理"""
    def get(self,request):
        # 1.获取查询参数中的code参数
        code = request.query_params.get('code')
        if not code:
            return Response({'message':'缺少code'},status=status.HTTP_400_BAD_REQUEST)

        oauth2 = OAuth_WEIBO(client_id=settings.APP_KEY,
                             client_key=settings.APP_SECRET,
                             redirect_url=settings.REDIRECT_URL, )
        try:
            access_token = oauth2.get_access_token(code)

        except Exception as error:
            logger.info(error)
            return Response({'message':'微博服务器异常'},status=status.HTTP_503_SERVICE_UNAVAILABLE)
        #4.查询openid是否绑定过美多商城中的用户
        try:
            wbauth_model = OAuthSinaUser.objects.get(access_token=access_token)
        except OAuthSinaUser.DoesNotExist:
            # 4.1未绑定
            #加密openid发送到前端，让前段暂时保存openid
            access_token = generate_save_user_token(access_token)
            return Response({'access_token':access_token})

        else:
            #4.2已绑定
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            user = wbauth_model.user
            payload = jwt_payload_handler(user)  # 生成载荷
            token = jwt_encode_handler(payload)  # 根据载荷生成token

            response = Response({
                'token':token,
                'username':user.username,
                'user_id':user.id
            })

            #做cookie购物车合并到redis操作
            merge_cart_cookie_to_redis(request, user, response)

            return response


    def post(self,request):
        #1.创建序列化器
        serializers=WBAuthUserSerializer(data=request.data)
        serializers.is_valid(raise_exception=True)
        user = serializers.save()

        #手动生成jwt token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(user)  # 生成载荷
        token = jwt_encode_handler(payload)  # 根据载荷生成token

        response = Response({
            'token': token,
            'username': user.username,
            'user_id': user.id
        })

        # 做cookie购物车合并到redis操作
        merge_cart_cookie_to_redis(request, user, response)

        return response

class WBAuthURLView(APIView):

    def get(self, request):

        oauth2 = OAuth_WEIBO(client_id=settings.APP_KEY,
                             client_key=settings.APP_SECRET,
                             redirect_url=settings.REDIRECT_URL)

        login_url = oauth2.get_auth_url()

        return Response({'login_url': login_url})

