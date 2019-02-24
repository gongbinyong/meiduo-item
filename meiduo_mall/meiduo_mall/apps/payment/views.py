import os

from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from orders.models import OrderInfo
from rest_framework.response import Response
from rest_framework import status
from alipay import AliPay
from django.conf import settings

# Create your views here.
from payment.models import Payment


class PaymentView(APIView):

    permission_classes = (IsAuthenticated, ) #验证登陆

    def get(self,request,order_id):
        """获取支付链接"""

        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"])

        except OrderInfo.DoesNotExist:
            return Response({'message':'订单信息有误'},status=status.HTTP_400_BAD_REQUEST)

        # 构造支付宝支付链接地址
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )

        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  #美多商城订单编号
            total_amount=str(order.total_amount),  #支付的总价  转字符串
            subject="美多商城%s" % order_id,
            return_url="http://www.meiduo.site:8080/pay_success.html",
        )

        alipay_url = settings.ALIPAY_URL + "?" + order_string
        return Response({'alipay_url': alipay_url})

class PaymentStatusView(APIView):
    def put(self,request):
        # query_params 获取查询参数中所有数据
        query_dict = request.query_params

        #把query_dict转换成字典
        data = query_dict.dict()

        #取出查询参数中的sign签名部分
        sign = data.pop('sign')

        #创建alipay支付对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )

        #调用alipay对象中的verify方法进行验证支付信息
        success = alipay.verify(data,sign) #返回True为验证成功 反之失败

        if success:

            #获取订单编号
            order_id = data.get('out_trade_no')
            #获取支付宝交易流水号
            trade_id = data.get('trade_no')

            try:
                Payment.objects.get(order_id=order_id)
            except:

                Payment.objects.create(
                    order_id=order_id,
                    trade_id=trade_id
                )

                # 修改订单状态
                OrderInfo.objects.filter(order_id=order_id, status=OrderInfo.ORDER_STATUS_ENUM['UNPAID']).update(
                    status=OrderInfo.ORDER_STATUS_ENUM["UNSEND"])
                return Response({'trade_id': trade_id})

            else:
                return Response({'trade_id': trade_id})

        else:
            return Response({'message':'非法请求'},status=status.HTTP_403_FORBIDDEN)

