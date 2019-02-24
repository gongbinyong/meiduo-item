from django.http import HttpResponse
from django_redis import get_redis_connection
from rest_framework.views import APIView


from meiduo.utils.captcha import captcha


class ImageCodes(APIView):
    def get(self,request,image):

        redis_conn = get_redis_connection('image')

        # 3.1 生成验证码图片，验证码图片的真实值
        image_name, real_image_code, image_data = captcha.captcha.generate_captcha()

        # 3.2 code_id作为key将验证码图片的真实值保存到redis数据库，并且设置有效时长(5分钟)
        try:
            redis_conn.setex("IMAGE_%s"%image, 300, real_image_code)
        except Exception as e:
            # current_app.logger.error(e)
            pass

        # 4.1 返回验证码图片(返回的数据是二进制格式，不能兼容所有浏览器)
        response = HttpResponse(image_data)
        # response.headers["Content-Type"] = "image/JPEG"
        return response