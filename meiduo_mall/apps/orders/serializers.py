from django.db import transaction
from rest_framework import serializers
from goods.models import SKU
from orders.models import OrderInfo, OrderGoods
from django.utils import timezone
from decimal import Decimal
from django_redis import get_redis_connection


class SaveOrderSerializer(serializers.ModelSerializer):
    """
    下单数据序列化器
    """
    class Meta:
        model = OrderInfo
        fields = ('order_id', 'address', 'pay_method')
        read_only_fields = ('order_id',)
        extra_kwargs = {
            'address': {
                'write_only': True,
                'required': True,
            },
            'pay_method': {
                'write_only': True,
                'required': True
            }
        }

    def create(self, validated_data):
        """保存订单"""
        # 获取当前下单用户
        user = self.context['request'].user

        # 组织订单编号 20170903153611+user.id
        # timezone.now() -> datetime
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + ('%09d' % user.id)

        address = validated_data['address']
        pay_method = validated_data['pay_method']

        # 开启一个事务
        with transaction.atomic():
            # 创建一个保存点
            save_point = transaction.savepoint()

            try:
                # 创建订单信息
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=0,
                    total_amount=Decimal(0),
                    freight=Decimal(10),
                    pay_method=pay_method,
                    status=OrderInfo.ORDER_STATUS_ENUM['UNSEND'] if pay_method == OrderInfo.PAY_METHODS_ENUM[
                        'CASH'] else OrderInfo.ORDER_STATUS_ENUM['UNPAID']
                )
                # 获取购物车信息
                redis_conn = get_redis_connection("cart")
                redis_cart = redis_conn.hgetall("cart_%s" % user.id)
                selected = redis_conn.smembers('selected_%s' % user.id)

                # 将bytes类型转换为int类型
                cart = {}
                for sku_id in selected:
                    cart[int(sku_id)] = int(redis_cart[sku_id])

                # 一次查询出所有商品数据
                skus = SKU.objects.filter(id__in=cart.keys())

                # 处理订单商品
                for sku in skus:
                    while True:
                        sku_count = cart[sku.id]

                        # 判断库存
                        origin_stock = sku.stock  # 原始库存
                        origin_sales = sku.sales  # 原始销量

                        if sku_count > origin_stock:
                            transaction.savepoint_rollback(save_point)
                            raise serializers.ValidationError('商品库存不足')

                        # 用于演示并发下单
                        # import time
                        # time.sleep(5)

                        # 减少库存
                        new_stock = origin_stock - sku_count
                        new_sales = origin_sales + sku_count

                        sku.stock = new_stock
                        sku.sales = new_sales
                        sku.save()

                        # 累计商品的SPU 销量信息
                        sku.goods.sales += sku_count
                        sku.goods.save()

                        # 保存订单商品
                        OrderGoods.objects.create(
                            order=order,
                            sku=sku,
                            count=sku_count,
                            price=sku.price,
                        )

                        # 累计订单基本信息的数据
                        order.total_count += sku_count  # 累计总金额
                        order.total_amount += (sku.price * sku_count)  # 累计总额

                        break

                # 更新订单的金额数量信息
                order.total_amount += order.freight
                order.save()

            except Exception as e:
                transaction.savepoint_rollback(save_point)
                raise

        # 提交事务
        transaction.savepoint_commit(save_point)

        # 更新redis中保存的购物车数据
        pl = redis_conn.pipeline()
        pl.hdel('cart_%s' % user.id, *selected)
        pl.srem('selected_%s' % user.id, *selected)
        pl.execute()
        return order

class CartSKUSerializer(serializers.ModelSerializer):
    """
    购物车商品数据序列化器
    """
    count = serializers.IntegerField(label='数量')

    class Meta:
        model = SKU
        fields = ('id', 'name', 'default_image_url', 'price', 'count')


class OrderSettlementSerializer(serializers.Serializer):
    """
    订单结算数据序列化器
    """
    freight = serializers.DecimalField(label='运费', max_digits=10, decimal_places=2)
    skus = CartSKUSerializer(many=True)