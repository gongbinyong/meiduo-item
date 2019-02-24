class CommentSerializer(serializers.ModelSerializer):
    """保存评价信息,
    OrderGoods的comment,score,is_anonymous,is_commented,
    OrderInfo的status,
    SKU的comments,
    """

    class Meta:
        model = OrderGoods
        fields = ['order', 'sku', 'comment', 'score', 'is_anonymous']
        extra_kwargs = {
            'order': {
                'write_only': True,
                'required': True,
            },
            'sku': {
                'write_only': True,
                'required': True
            }
        }

    def update(self, instance, validated_data):
        order = validated_data.get('order')
        sku = validated_data.get('sku')
        comment = validated_data.get('comment')
        score = validated_data.get('score')
        is_anonymous = validated_data.get('is_anonymous')
        with transaction.atomic():
            save_point = transaction.savepoint()
            try:
                order_goods = OrderGoods.objects.get(order_id=order)
                order_goods.comment = comment
                order_goods.score = score
                order_goods.is_anonymous = is_anonymous
                order_goods.is_commented = True
                order_goods.save()
                sku.comments += 1
                sku.save()
            except Exception as e:
                transaction.savepoint_rollback(save_point)
                raise serializers.ValidationError("商品评论失败")
            else:
                transaction.savepoint_commit(save_point)
            return order_goods


class SKUInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = ['name']


class UncommentSerializer(serializers.ModelSerializer):
    sku = SKUInfoSerializer()

    class Meta:
        model = OrderGoods
        fields = ["sku", "price"]


class SKUCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(label="用户名")

    class Meta:
        model = OrderGoods
        fields = ['score', 'comment', 'username']