from django.db import models
from users.models import User

from meiduo.utils.models import BaseModel
# Create your models here.


class OAuthQQUser(BaseModel):
    user = models.ForeignKey(User, verbose_name='关联用户', on_delete=models.CASCADE)
    openid = models.CharField(verbose_name='QQ用户唯一标识', db_index=True, max_length=64)

    class Meta:
        db_table = 'tb_qq_auth'
        verbose_name = 'QQ登录用户数据'
        verbose_name_plural = verbose_name
