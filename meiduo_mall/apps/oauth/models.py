from django.db import models
from meiduo_mall.utils.models import BasrModel
from users.models import User
# Create your models here.

class QQAuthUser(BasrModel):
    user = models.ForeignKey(User,verbose_name='openid关联的用户',on_delete=models.CASCADE)
    openid = models.CharField(verbose_name='QQ用户唯一标识',max_length=64,db_index=True)

    class Meta:
        db_table = 'tb_oauth_qq'
        verbose_name = 'QQ登录用户数据'
        verbose_name_plural = verbose_name