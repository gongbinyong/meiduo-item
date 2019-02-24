#编写异步任务代码
from celery_tasks.sms.yuntongxun.sms import CCP
from . import constants
from celery_tasks.main import celery_app


@celery_app.task(name='send_sms_code') #用celery_app调用task装饰函数为异步函数
def send_sms_code(mobile,sms_code):

    CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES // 60], 1)