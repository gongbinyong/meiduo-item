from decimal import Decimal
import time

from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, UpdateAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from goods.models import SKU
from orders.models import OrderInfo, OrderGoods
from .serializers import OrderSettlementSerializer, CommitOrderSerializer, GetOrdersSerializer


class OrderSettlementView(APIView):
    """去结算接口"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        redis_conn = get_redis_connection('cart')
        redis_cart = redis_conn.hgetall("cart_%d" % user.id)
        cart_selected = redis_conn.smembers("selected_%d" % user.id)
        cart = {}
        for sku_id in cart_selected:
            cart[int(sku_id)] = int(redis_cart[sku_id])
        skus = SKU.objects.filter(id__in=cart.keys())
        for sku in skus:
            sku.count = cart[sku.id]
        freight = Decimal('10.00')
        serializer = OrderSettlementSerializer({"freight": freight, 'skus': skus})

        return Response(serializer.data)


class CommitOrderView(CreateAPIView):
    # 指定权限
    permission_classes = [IsAuthenticated]

    # 指定序列化器
    serializer_class = CommitOrderSerializer


    # def get(self, request):
    #     orders = self.get_queryset()
    #     serializer = GetOrdersSerializer(orders, many=True)
    #     return Response(serializer.data)


class GetOrdersView(ListAPIView):
    """获取订单列表"""
    permission_classes = [IsAuthenticated]
    serializer_class = GetOrdersSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = OrderInfo.objects.filter(user=user).order_by('order_id')
        for order in queryset:
            order.create_time = order.create_time.strftime('%Y-%m-%d %H:%M:%S')
        return queryset



