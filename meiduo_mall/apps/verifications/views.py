from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from random import randint
from django_redis import get_redis_connection
from meiduo_mall.libs.yuntongxun.sms import CCP
from rest_framework.response import Response
import logging
from . import constants
from celery_tasks.sms.tasks import send_sms_code

logger= logging.getLogger('django')

# Create your views here.

class SMSCodeView(APIView):
    def get(self,request,mobile):

        # 0.创建redis链接对象
        redis_conn = get_redis_connection('verify_codes')

        flag = redis_conn.get('sms_flag_%s' %mobile)
        if flag:
            return Response({'message':'发送短信频繁'},status=status.HTTP_400_BAD_REQUEST)

        #1.生成验证码
        sms_code = '%06d'% randint(0,999999)
        logger.info(sms_code)

        pl=redis_conn.pipeline()
        #2.把验证码保存到redis中
        #redis_conn.setex('sms_%s' %mobile,constants.SMS_CODE_REDIS_EXPIRES,sms_code)
        pl.setex('sms_%s' %mobile,constants.SMS_CODE_REDIS_EXPIRES,sms_code)
        #3.1
        #redis_conn.setex('sms_flag_%s' %mobile,constants.SEND_SMS_CODE_INTERVAL,1)
        pl.setex('sms_flag_%s' % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)

        pl.execute()
        #4.利用荣联云发送短信
        send_sms_code.delay(mobile,sms_code)
        #CCP().send_template_sms(mobile,[sms_code,constants.SMS_CODE_REDIS_EXPIRES // 60],1)

        return Response({'message':'OK'})

