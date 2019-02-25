from django.shortcuts import render

# Create your views here.
import pickle, base64
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from goods.models import SKU
from .serializers import CartSerializer, CartSKUSerializer, CartDeleteSerializer, CartSelectedSerializer


class CartView(APIView):
    def perform_authentication(self, request):
        """禁用认证/延后认证"""
        pass

    def post(self, request):
        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data.get('sku_id')
        count = serializer.validated_data.get('count')
        selected = serializer.validated_data.get('selected')
        response = Response(data=serializer.data, status=status.HTTP_201_CREATED)

        try:
            user = request.user
            redis_conn = get_redis_connection('cart')
            pl = redis_conn.pipeline()
            pl.hincrby('cart_%d' % user.id, sku_id, count)
            if selected:
                pl.sadd('selected_%d' % user.id, sku_id)
            pl.execute()

        except:
            cart_cookie = request.COOKIES.get('carts')
            if cart_cookie:
                cart_dict = pickle.loads(base64.b64decode(cart_cookie.encode()))
                if sku_id in cart_dict:
                    count += cart_dict[sku_id]['count']
            else:
                cart_dict = {}
            cart_dict[sku_id] = {
                'count': count,
                'selected': selected
            }
            cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            response.set_cookie('carts', cart_str)
        return response

    def get(self, request):
        try:
            user = request.user
        except:
            user = None
        else:
            redis_conn = get_redis_connection('cart')
            cart_redis_dict = redis_conn.hgetall('cart_%d' % user.id)
            selected_ids = redis_conn.smembers('selected_%d' % user.id)
            cart_dict = {}
            for sku_id_bytes in cart_redis_dict:
                cart_dict[int(sku_id_bytes)] = {
                    "count": int(cart_redis_dict[sku_id_bytes]),
                    "selected": sku_id_bytes in selected_ids
                }
        if not user:
            cart_str = request.COOKIES.get("carts")
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict = {}
        skus = SKU.objects.filter(id__in=cart_dict.keys())
        for sku in skus:
            sku.count = cart_dict[sku.id]["count"]
            sku.selected = cart_dict[sku.id]["selected"]
        serializer = CartSKUSerializer(skus, many=True)
        return Response(serializer.data)

    def put(self, request):
        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data.get('sku_id')
        count = serializer.validated_data.get('count')
        selected = serializer.validated_data.get('selected')
        response = Response(data=serializer.data)
        try:
            user = request.user
        except:
            user = None
        else:
            redis_conn = get_redis_connection('cart')
            pl = redis_conn.pipeline()
            pl.hset('cart_%d' % user.id, sku_id, count)
            if selected:
                pl.sadd('selected_%d' % user.id, sku_id)
            else:
                pl.srem('selected_%d' % user.id, sku_id)
            pl.execute()
        if not user:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
                if sku_id in cart_dict:
                    cart_dict[sku_id] = {
                        'count': count,
                        'selected': selected
                    }
                cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
                response.set_cookie('carts', cart_str)
        return response

    def delete(self, request):
        serializer = CartDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data.get("sku_id")
        response = Response(status=status.HTTP_204_NO_CONTENT)
        try:
            user = request.user
        except:
            user = None
        else:
            redis_conn = get_redis_connection('cart')
            pl = redis_conn.pipeline()
            pl.hdel('cart_%d' % user.id, sku_id)
            pl.srem('selected_%d' % user.id, sku_id)
            pl.execute()
        if not user:
            cart_str = request.COOKIES.get("carts")
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
                if sku_id in cart_dict:
                    del cart_dict[sku_id]
                if len(cart_dict.keys()):
                    cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
                    response.set_cookie("carts", cart_str)
                else:
                    response.delete_cookie("carts")
        return response


class CartSelectedView(APIView):
    def perform_authentication(self, request):
        """禁用认证/延后认证"""
        pass

    def put(self, request):
        serializer = CartSelectedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected = serializer.validated_data.get("selected")
        response = Response(serializer.data)
        try:
            user = request.user
        except:
            user = None
        else:
            redis_conn = get_redis_connection("cart")
            cart_redis_dict = redis_conn.hgetall("cart_%d" % user.id)
            if selected:
                redis_conn.sadd("selected_%d" % user.id, *cart_redis_dict.keys())
            else:
                redis_conn.srem("selected_%d" % user.id, *cart_redis_dict.keys())
        if not user:
            cart_str = request.COOKIES.get("carts")
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
                for sku_id in cart_dict:
                    cart_dict[sku_id]["selected"] = selected
                cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
                response.set_cookie("carts", cart_str)
        return response
