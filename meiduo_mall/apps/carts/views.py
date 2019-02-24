from django.shortcuts import render

# Create your views here.

from rest_framework.views import APIView

from carts.serialziers import CartSerializer,CartSKUSerializer,CartDeleteSerializer,CartSelectAllSerializer
import pickle,base64
from rest_framework.response import Response
from rest_framework import status
from django_redis import get_redis_connection

from goods.models import SKU


class CartView(APIView):
    """购物车视图"""

    def perform_authentication(self, request):
        """
        重写父类的用户验证方法，不在进入视图前就检查JWT
        """
        pass

    def post(self, request):
        """添加购物车"""

        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data.get('sku_id')
        count = serializer.validated_data.get('count')
        selected = serializer.validated_data.get('selected')

        response = Response(serializer.data, status=status.HTTP_201_CREATED)

        try:
            user = request.user

            # 创建redis连接对象
            redis_conn = get_redis_connection('cart')
            pl = redis_conn.pipeline()

            pl.hincrby('cart_%d' % user.id, sku_id, count)

            if selected:  # 判断当前商品是否勾选, 把勾选的商品sku_id添加到set集合中
                pl.sadd('selected_%d' % user.id, sku_id)
            pl.execute()

        except:
            #获取cookie中的购物车数据
            cart_cookie = request.COOKIES.get('carts')
            #判断是否有购物车数据
            if cart_cookie:
                # 把字符串转python中的字典
                cart_cookie_bytes = cart_cookie.encode()
                cart_ascii_bytes=base64.b64decode(cart_cookie_bytes)
                cart_dict=pickle.loads(cart_ascii_bytes)

            else: #之前没有购物车数据
                cart_dict = {}
            # 判断本次添加的商品在购物车中是否已存在 如果在 增量计算

            if sku_id in cart_dict:
                origin_count=cart_dict[sku_id]['count']
                count += origin_count

            cart_dict[sku_id]={
                'count':count,
                'selected':selected
            }

            cart_ascii_bytes=pickle.dumps(cart_dict)
            cart_cookie_bytes=base64.b64encode(cart_ascii_bytes)
            cart_str=cart_cookie_bytes.decode()

            # 创建相应对象
            response.set_cookie('carts',cart_str)

        return response

    def get(self, request):
        """查询购物车"""

        try:
            user = request.user
        except:
            user=None
        else:
            # 获取到user 说明是登录用户 操作redis
            redis_conn = get_redis_connection('cart')
            cart_redis_dict = redis_conn.hgetall('cart_%s' % user.id)
            selected_ids = redis_conn.smembers('selected_%d'%user.id)

            # 定义一个大字典
            cart_dict={}
            for sku_id_bytes in cart_redis_dict:
                cart_dict[int(sku_id_bytes)]={
                    'count': int(cart_redis_dict[sku_id_bytes]),
                    'selected': sku_id_bytes in selected_ids
                }

        if not user:
            cart_str = request.COOKIES.get('carts')
            # 判断是否有cookie购物车数据
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                cart_dict={}

        # 获取购物车中所有商品的sku模型
        skus=SKU.objects.filter(id__in=cart_dict.keys())
        for sku in skus:
            sku.count=cart_dict[sku.id]['count']
            sku.selected=cart_dict[sku.id]['selected']

        serializer = CartSKUSerializer(skus,many=True)

        return Response(serializer.data)

    def put(self, request):
        """修改购物车"""

        serializer=CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True) #校验
        sku_id=serializer.validated_data.get('sku_id')
        count=serializer.validated_data.get('count')
        selected=serializer.validated_data.get('selected')

        response = Response(serializer.data)
        try:
            user=request.user
        except:
            user=None
        else:
            #已登陆
            redis_conn = get_redis_connection('cart')
            pl=redis_conn.pipeline()
            #修改商品数量   把字典中的hash的sku_id的value改掉
            pl.hset('cart_%s'%user.id,sku_id,count)

            if selected:
                pl.sadd('selected_%d' % user.id, sku_id)
            else:
                pl.srem('selected_%d' % user.id, sku_id)
            pl.execute()

        if not user:
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))

                if sku_id in cart_dict: #判断当前要修稿的sku_id 在cookie字典中是否存在
                    #直接覆盖商品的数量及勾选状态
                    cart_dict[sku_id] = {
                        'count':count,
                        'selected':selected
                    }
                cart_str=base64.b64encode(pickle.dumps(cart_dict)).decode()
                response.set_cookie('carts',cart_str)

        return response

    def delete(self, request):
        """删除购物车"""
        """
                删除购物车数据
                """
        serializer = CartDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data['sku_id']

        response = Response(status=status.HTTP_204_NO_CONTENT)

        try:
            user = request.user
        except Exception:
            # 验证失败，用户未登录
            user = None

        if user is not None and user.is_authenticated:
            # 用户已登录，在redis中保存
            redis_conn = get_redis_connection('cart')

            pl = redis_conn.pipeline()
            pl.hdel('cart_%s' % user.id, sku_id)
            pl.srem('selected_%s' % user.id, sku_id)

            pl.execute()

        else:
            # 用户未登录，在cookie中保存

            # 使用pickle序列化购物车数据，pickle操作的是bytes类型
            cart_str = request.COOKIES.get('carts')

            if cart_str:
                cart_dict= pickle.loads(base64.b64decode(cart_str.encode()))

                if sku_id in cart_dict:
                    del cart_dict[sku_id]

                if len(cart_dict.keys()): # 表示cookie字典中还有商品
                    cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
                        # 设置购物车的cookie
                        # 需要设置有效期，否则是临时cookie
                    response.set_cookie('carts', cart_str)
                else:
                    response.delete_cookie('carts')

        return response

class CartSelectAllView(APIView):
    """
    购物车全选
    """
    def perform_authentication(self, request):
        """
        重写父类的用户验证方法，不在进入视图前就检查JWT
        """
        pass

    def put(self, request):
        serializer = CartSelectAllSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected = serializer.validated_data['selected']

        response = Response({'message': 'OK'})

        try:
            user = request.user
        except:
            # 验证失败，用户未登录
            user = None
        else:
            # 用户已登录，在redis中保存
            redis_conn = get_redis_connection('cart')
            cart = redis_conn.hgetall('cart_%s' % user.id)
            sku_id_list = cart.keys()

            if selected:
                # 全选
                redis_conn.sadd('selected_%s' % user.id, *sku_id_list)
            else:
                # 取消全选
                redis_conn.srem('selected_%s' % user.id, *sku_id_list)

        if not user:
            # cookie
            cart = request.COOKIES.get('carts')

            if cart is not None:
                cart = pickle.loads(base64.b64decode(cart.encode()))
                for sku_id in cart:
                    cart[sku_id]['selected'] = selected
                cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()
                # 设置购物车的cookie
                # 需要设置有效期，否则是临时cookie
                response.set_cookie('carts', cookie_cart)

        return response