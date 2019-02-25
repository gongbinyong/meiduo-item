import pickle, base64
from django_redis import get_redis_connection

def merge_cart_cookie_to_redis(request, user, response):
    cart_str = request.COOKIES.get("carts")
    if not cart_str:
        return
    cookie_cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
    for sku_id in cookie_cart_dict:
        redis_conn = get_redis_connection("cart")
        redis_conn.hset('cart_%d' % user.id, sku_id, cookie_cart_dict[sku_id]['count'])
        if cookie_cart_dict[sku_id]['selected']:
            redis_conn.sadd('selected_%d' % user.id, sku_id)
    response.delete_cookie('carts')
