from django.db import models


class BasrModel(models.Model):
    create_time = models.DateTimeField(verbose_name='创建数据时间',auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        abstract = True #此模型是个抽象模型，将来迁移建表时，不会对他进行迁移建表动作，他只用来当作其他类的基类