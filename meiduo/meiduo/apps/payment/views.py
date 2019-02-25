import os

from alipay import AliPay
from django.conf import settings
from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from orders.models import OrderInfo


class PaymentView(APIView):
    """生成支付宝登录url"""
    permission_classes = [IsAuthenticated]  # 必须是登录用户才能访问此视图

    def get(self, request, order_id):
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'])
        except OrderInfo.DoesNotExist:
            return Response({'message': '订单信息有误'}, status=status.HTTP_400_BAD_REQUEST)
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/app_private_key.pem'),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                'keys/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )
        # 调用它里面的方法 生成支付宝登录url后面的 查询参数部分
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 美多商城订单编号
            total_amount=str(order.total_amount),  # 注意: 一定要把总价转换成字符串类型,不然会报错
            subject='美多商城%s' % order_id,  # 注意:如果变量是字条串类型必须用%s占位,如果变量是int类型可以用%d也可以用%s占位
            return_url="http://www.meiduo.site:8080/pay_success.html",  # 支付成功后的回调url
        )
        # 拼接完整 支付宝登录url
        # 沙箱环境 : 	https://openapi.alipaydev.com/gateway.do? + 查询参数部分

        # 真实环境 : 	https://openapi.alipay.com/gateway.do? + 查询参数部分  order_id=xxx&a=xxx
        alipay_url = settings.ALIPAY_URL + '?' + order_string

        return Response({'alipay_url': alipay_url})


class PaymentStatusView(APIView):
    def put(self, request):
        query_dict = request.query_params
        data = query_dict.dict()
        # 把查询参数中的sign签名部分数据单独提取出
        sign = data.pop('sign')
        alipay = AliPay(
            appid=settings,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys/app_private_key.pem'),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                'keys/alipay_public_key.pem'),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )
        success = alipay.verify(data, sign)
        if success:
            order_id = data.get("out_trade_no")
            trade_id = data.get("trade_no")
            try:
                Payment.objects.get(order_id=order_id)
            except:
                Payment.objects.create(order_id=order_id, trade_id=trade_id)
                OrderInfo.objects.filter(order_id=order_id, status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"]).update(
                    status=OrderInfo.ORDER_STATUS_ENUM["UNSEND"])
            else:
                pass
            return Response({"trade_id": trade_id})
        else:
            return Response({'message': '非法请求'}, status=status.HTTP_403_FORBIDDEN)
