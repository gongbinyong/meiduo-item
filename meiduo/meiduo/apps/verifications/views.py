import logging
from random import randint
from django.shortcuts import render
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from celery_tasks.sms.tasks import send_sms_code
from .constants import SEND_SMS_CODE_INTERVAL, SMS_CODE_REDIS_EXPIRES


logger = logging.getLogger("django")


class SMSCodeView(APIView):
    def get(self, request, mobile):
        redis_conn = get_redis_connection('verify_codes')
        flag = redis_conn.get("flag_%s" % mobile)
        if flag:
            return Response({'message': "请勿频繁发送短信"}, status=status.HTTP_400_BAD_REQUEST)
        sms_code = '%06d' % (randint(0, 999999))
        logger.info(sms_code)
        pl = redis_conn.pipeline()
        pl.setex(mobile, SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex("flag_%s" % mobile, SEND_SMS_CODE_INTERVAL, 1)
        pl.execute()
        send_sms_code.delay(mobile, sms_code)
        return Response({'message': 'ok'})


class AccessSMSCodeView(APIView):
    def get(self, request):

        # 获取token
        access_token = request.query_params.get('access_token')
        if not access_token:
            return Response({'message': '缺少token'}, status=status.HTTP_400_BAD_REQUEST)

        # 验证token
        # 0.创建redis链接对象
        redis_conn = get_redis_connection('verify_codes')
        mobile = redis_conn.get('TOCKEN_%s'% access_token).decode()

        if mobile is None:
            return Response({'message': '发送短信验证码失败'}, status=status.HTTP_400_BAD_REQUEST)

        flag = redis_conn.get('sms_flag_%s' % mobile)
        if flag:
            return Response({'message': '发送短信频繁'}, status=status.HTTP_400_BAD_REQUEST)
        # 1.生成验证码
        sms_code = '%06d' % randint(0, 999999)
        logger.info(sms_code)

        pl = redis_conn.pipeline()
        # 2.把验证码保存到redis中
        # redis_conn.setex('sms_%s' %mobile,constants.SMS_CODE_REDIS_EXPIRES,sms_code)
        pl.setex('sms_%s' % mobile, SMS_CODE_REDIS_EXPIRES, sms_code)

        pl.setex('sms_code_%s' %sms_code, SMS_CODE_REDIS_EXPIRES, mobile)
        # 3.1
        # redis_conn.setex('sms_flag_%s' %mobile,constants.SEND_SMS_CODE_INTERVAL,1)
        pl.setex('sms_flag_%s' % mobile, SEND_SMS_CODE_INTERVAL, 1)

        pl.execute()
        # 4.利用荣联云发送短信
        send_sms_code.delay(mobile, sms_code)

        return Response({'message':'OK'})