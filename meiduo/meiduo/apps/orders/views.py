from decimal import Decimal
import time

from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.generics import CreateAPIView, ListAPIView, UpdateAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from goods.models import SKU
from orders.models import OrderInfo, OrderGoods
from .serializers import OrderSettlementSerializer, CommitOrderSerializer, GetOrdersSerializer, SKUCommentSerializer, \
    CommentSerializer, UncommentSerializer


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


class SKUCommentView(GenericAPIView):
    filter_backends = [OrderingFilter]
    # 指定排序字段
    ordering_fields = ['-create_time']

    def get(self,request,sku_id):
        query_sets = OrderGoods.objects.filter(sku_id=sku_id, is_commented=True)
        for query_set in query_sets:
            if query_set.is_anonymous:
                query_set.username = "***"
            else:
                query_set.username = query_set.order.user.username
        serializer = SKUCommentSerializer(instance=query_sets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CommentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        try:

            order = OrderInfo.objects.get(order_id=order_id)
        except OrderInfo.DoesNotExist:
            response = Response({"message": "订单号有误"},status=status.HTTP_400_BAD_REQUEST)
        else:
            serializer = CommentSerializer(instance=order, data=request.data)
            serializer.is_valid()
            serializer.save()
            order_goods = OrderGoods.objects.filter(order_id=order_id)
            flag = True
            for goods in order_goods:
                if not goods.is_commented:
                    flag = False
            if flag:
                order.status = 5
                order.save()
            response = Response(serializer.data, status=status.HTTP_200_OK)
        return response


class UncommentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            OrderInfo.objects.get(order_id=order_id, status=4)
        except OrderInfo.DoesNotExist:
            return Response({"message": "xxx"}, status=status.HTTP_400_BAD_REQUEST)
        query_sets = OrderGoods.objects.filter(order_id=order_id, is_commented=False)
        serializer = UncommentSerializer(query_sets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



