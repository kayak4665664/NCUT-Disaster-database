# NCUT-Disaster-database
A database that records disasters in China, including earthquakes, floods, fires, mine disasters, explosions, and air disasters. It supports automatic data import and visual display.  
一个记录中国灾害的数据库，包括地震、水灾、火灾、矿难、爆炸和空难。它支持数据自动导入以及可视化展示。

Time: 2021 Summer

## Details 细节
1. Mainly uses the `Django`, and also uses `layui` for front-end design. 主要使用了`Django`框架，另外使用了`layui`用于前端设计。
2. The database uses `Django models` based on `SQLite3`. 数据库使用了基于`SQLite3`的`Django 模型`。
3. Gets titles and articles using the `newspaper`. 使用`newspaper`获取标题与文章。
4. Takes screenshots of web pages using `selenium` and `google chrome`. 使用`selenium`和`google chrome`获取网页截图。
5. Converts Traditional Chinese to Simplified using `langconv`. 使用`langconv`转换繁体中文至简体。
6. Automatically extracts information from Chinese using `jieba`. 使用`jieba`自动从中文中提取信息。
7. Automatically extract Chinese article abstracts using `textrank4zh`. 使用`textrank4zh`自动提取中文文章摘要。
8. Data Visualization with `Highcharts`. 通过`Highcharts`进行数据可视化。

## Database 数据库
`models.py`:
``` python
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
```

## Functions 功能
1. importing data manually 手动导入数据
2. importing data automatically 自动导入数据 (Uses multithreading 使用多线程)
3. data correction 校正数据 (For automatically imported data 针对自动导入的数据)
4. data modification 修改数据
5. data visualization 数据可视化 (Timelines, pie charts, bar charts, and maps 时间轴、饼图、条形图和地图)
6. data mining 数据挖掘 (Mining keywords and topic summaries 挖掘关键词与主题摘要)