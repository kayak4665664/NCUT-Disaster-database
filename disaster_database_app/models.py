from django.db import models

class Disaster(models.Model):
    is_corrected = models.BooleanField()  # 是否已校正
    url = models.TextField()  # 网页地址
    text = models.TextField()  # 正文
    title = models.TextField()  # 标题
    time = models.TextField()  # 时间
    location = models.TextField()  # 地点
    province = models.TextField(null=True)  # 一级行政区
    prefecture = models.TextField(null=True)  # 二级行政区
    category = models.TextField()  # 灾难类型
