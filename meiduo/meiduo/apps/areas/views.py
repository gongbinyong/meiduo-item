from django.shortcuts import render
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_extensions.cache.mixins import CacheResponseMixin

# Create your views here.
from .models import Area
from .serializers import AreaSerializer, SubsAreaSerializer


class AreasViewSet(CacheResponseMixin, ReadOnlyModelViewSet):
    """省市区查询视图集"""
    pagination_class = None

    def get_queryset(self):
        if self.action == 'list':  # 如果是list行为表示要所有省的模型
            return Area.objects.filter(parent_id=None)
        else:
            return Area.objects.all()

    # serializer_class = AreaSerializer
    def get_serializer_class(self):
        if self.action == 'list':
            return AreaSerializer
        else:
            return SubsAreaSerializer
