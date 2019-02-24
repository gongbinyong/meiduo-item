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
