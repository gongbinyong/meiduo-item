from django.shortcuts import render
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_redis import get_redis_connection
from goods.models import SKU
from decimal import Decimal
from . import serializers
from orders.models import OrderInfo
import time
# Create your views here.


class GetOrdersView(ListAPIView):
    permission_classes = [IsAuthenticated]

    serializer_class = serializers.GetOrdersSerializer

    def get_queryset(self):
        user = self.request.user
        orders = OrderInfo.objects.filter(user_id=user.id)
        for order in orders:
            order.create_time = order.create_time.strftime('%Y-%m-%d %H:%M:%S')
        return orders

    # def get():
    #
    #     user = request.user
    #
    #     orders = OrderInfo.objects.filter(user_id=user.id)
    #
    #     serializer = serializers.GetOrdersSerializer(orders)
    #
    #     return Response(serializer.data)

class SaveOrderView(CreateAPIView):
    """
    保存订单
    """
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.SaveOrderSerializer

class OrderSettlementView(APIView):
    """
    订单结算
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取"""
        user = request.user

        # 从购物车中获取用户勾选要结算的商品信息
        redis_conn = get_redis_connection('cart')
        redis_cart = redis_conn.hgetall('cart_%s' % user.id)
        cart_selected = redis_conn.smembers('selected_%s' % user.id)

        cart = {}
        for sku_id in cart_selected:
            cart[int(sku_id)] = int(redis_cart[sku_id])

        # 查询商品信息
        skus = SKU.objects.filter(id__in=cart.keys())
        for sku in skus:
            sku.count = cart[sku.id]

        # 运费
        freight = Decimal('10.00')
        # 创建序列化器时 给instance参数可以传递(模型/查询集(many=True) /字典)
        serializer = serializers.OrderSettlementSerializer({'freight': freight, 'skus': skus})

        return Response(serializer.data)
