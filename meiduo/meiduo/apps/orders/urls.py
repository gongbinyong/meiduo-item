from django.conf.urls import url

from . import views

urlpatterns = [
    # 去结算
    url(r'^orders/settlement/$', views.OrderSettlementView.as_view()),
    # 保存订单
    url(r'^order/$', views.CommitOrderView.as_view()),
    # 获取全部订单
    url(r'^orders/$', views.GetOrdersView.as_view()),
    # 获取未评价订单商品
    url(r'^orders/(?P<order_id>\d{23})/uncommentgoods/$', views.UncommentView.as_view()),
    # 保存商品评价
    url(r'^orders/(?P<order_id>\d{23})/comments/$', views.CommentView.as_view()),
    # 商品评价展示
    url(r'^skus/(?P<sku_id>\d+)/comments/$', views.SKUCommentView.as_view()),

]