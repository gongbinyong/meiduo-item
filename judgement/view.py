class SKUCommentView(GenericAPIView):
    filter_backends = [OrderingFilter]
    # 指定排序字段
    ordering_fields = ['-create_time']

    def get(self,request,sku_id):
        query_sets = OrderGoods.objects.filter(sku_id=sku_id)
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

