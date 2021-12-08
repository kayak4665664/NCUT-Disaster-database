from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from disaster_database_app.models import Disaster
import newspaper
from newspaper import Article
from selenium import webdriver
import os.path
from selenium.webdriver.chrome.options import Options
from pathlib import Path
import threading
import jieba.posseg as psg
import jieba.analyse
import csv
from django.conf import settings
from .langconv import *
from textrank4zh import TextRank4Sentence
import re


def Traditional2Simplified(sentence):  # 将繁体中文文本翻译为简体中文
    sentence = Converter('zh-hans').convert(sentence)
    return sentence


def save_web_shot(url, filename):  # 下载网页快照
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.binary_location = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    chrome_driver_binary = '/usr/local/bin/chromedriver'
    driver = webdriver.Chrome(chrome_driver_binary, chrome_options=options)
    driver.maximize_window()
    js_height = 'return document.body.clientHeight'
    try:
        driver.get(url)
        scroll_width = driver.execute_script(
            'return document.body.parentNode.scrollWidth')
        driver.set_window_size(scroll_width, 1000)
        filepath = os.path.join(
            Path(__file__).resolve().parent.parent, 'statics/images/') + filename + '.png'
        driver.get_screenshot_as_file(filepath)
    except Exception as e:
        print(e)


def time_location_extract(text):  # 对正文进行分词，自动获取时间和地点
    time_res = set()
    location_res = set()
    time_word = ''
    location_word = ''
    for k, v in psg.cut(text):
        if time_word != '':
            if v in ['m', 't']:
                time_word = time_word + k
            else:
                time_res.add(time_word)
                time_word = ''
        elif v in ['m', 't']:
            time_word = k
        if location_word != '':
            if v == 'ns':
                location_word = location_word + k
            else:
                location_res.add(location_word)
                location_word = ''
        elif v == 'ns':
            location_word = k
    if time_word != '':
        time_res.add(time_word)
    if location_word != '':
        location_res.add(location_word)
    time = ''
    for s in set(filter(lambda x: '日' in x, time_res)):
        if len(time) > 0:
            time += '、'
        time += s
    location = ''
    for s in location_res:
        if len(location) > 0:
            location += '、'
        location += s
    return [time, location]


def auto_import_data(url):  # 自动导入数据
    if Disaster.objects.filter(url=url).count() > 0:  # 若已经导入此灾难事件
        return
    try:
        news = Article(url, language='zh')
        news.download()  # 爬取网页数据
        news.parse()
        extract_res = time_location_extract(news.text)  # 对正文进行分词，自动获取时间和地点
        text = Traditional2Simplified(news.text)  # 将文本中的繁体中文翻译为简体中文
        if text is None:
            text = ''
        title = Traditional2Simplified(news.title)  # 将标题中的繁体中文翻译为简体中文
        if title is None:
            title = ''
        time = extract_res[0]
        location = extract_res[1]
        category = '未知'  # 自动判断灾难类型
        if '地震' in text:
            category = '地震'
        elif '洪涝' in text or '暴雨' in text or '水灾' in text or '雨灾' in text or '泥石流' in text or '洪水' in text:
            category = '水灾'
        elif '矿难' in text:
            category = '矿难'
        elif '空难' in text:
            category = '空难'
        elif '火灾' in text:
            category = '火灾'
        elif '爆炸' in text:
            category = '爆炸'
        disaster = Disaster(is_corrected=False, url=url, text=text,
                            title=title, time=time, location=location, category=category)
        disaster.save()  # 将数据存入数据库中
        id = str(Disaster.objects.filter(url=url).values()[0]['id'])
        save_web_shot(url, id)  # 下载网页快照
    except Exception as e:
        print(e)


stop_words = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '编辑', '年月日', '发生', '时分', '造成', '现场', '人员', '事发', '导致', '日时', '其中', '影响', '地区', '位于', '当时', '表示', '小时',
              '进行', '此次', '灾情', '附近', '上午', '下午', '机上', '由于', '相关', '部分', '本次', '编号', '原因', '发现', '当地', '前往', '工作', '经过', '事故', '事件', '中国', '中华民国', '公里', '灾区', '出现', 'UTC', '千米', '毫米', '没有', '发布', '人数', '中心', '飞往', '中华人民共和国', '包括', '地点', '时任', '情况', '无法', '一名', '林彪', '一架', '万元', '要求', '认为', '参考文献', '点分', '该次', '活动', '--', '以上', '根据', '这次', '亿元', '县', '省', '市', '万人', '立方米', '截至', '录得', '每秒', '发出', '达到', '以来', '次列车', '中队', '二楼', '日期', '工程', '箱涵', '事后', '到场', '共人', '时许', '位置', '成立', '当日', '灾变', '条目', '该矿', '中共', '副长', '决定', '赶赴', '给予', '万吨', '委副', '健二', '中华', '毛泽东', '主席', '分钟', '周恩来', 'CI', '最终', '叶群', '当天', '解放军', '人民', '吴法宪', '该机', '之后', '抵达', '立即', '委员会', '黄裕']  # 停用词列表


def get_summary(text, num):  # 挖掘摘要与主题
    tr4s = TextRank4Sentence()
    tr4s.analyze(text=text, lower=True, source='all_filters')
    return [item.sentence for item in tr4s.get_key_sentences(num)]


@csrf_exempt
def disaster(request):
    func = 'manual_import'
    if request.method == 'GET':
        manual_import = request.GET.get('manual_import')
        if manual_import == 'True':  # 手动导入数据功能
            url = request.GET.get('url')  # 网页地址
            category = request.GET.get('category')  # 灾难类型
            time = request.GET.get('time')  # 时间
            province = request.GET.get('province')  # 一级行政区
            prefecture = request.GET.get('prefecture')  # 二级行政区
            if Disaster.objects.filter(url=url).count() > 0:  # 若已经导入此灾难事件
                # 返回错误信息
                return render(request, 'disaster.html', {'func': 'manual_import', 'is_manual_import': 'Faile'})
            try:
                news = Article(url, language='zh')
                news.download()  # 爬取网页数据
                news.parse()
                text = Traditional2Simplified(news.text)  # 将文本中的繁体中文转换为简体中文
                if text is None:
                    text = ''
                title = Traditional2Simplified(news.title)  # 将标题中的繁体中文转换为简体中文
                if title is None:
                    title = ''
                location = province + prefecture  # 地点
                disaster = Disaster(is_corrected=True, url=url, text=text, title=title, time=time,
                                    location=location, province=province, prefecture=prefecture, category=category)
                disaster.save()  # 将数据存入数据库中
                id = str(Disaster.objects.filter(
                    url=url).values()[0]['id'])  # 获取主键id
                threading.Thread(target=save_web_shot, args=(
                    url, id)).start()  # 启动下载网页快照线程，用id作为文件名
                # 返回正确信息
                return render(request, 'disaster.html', {'func': 'manual_import', 'is_manual_import': 'True'})
            except:
                # 返回错误信息
                return render(request, 'disaster.html', {'func': 'manual_import', 'is_manual_import': 'False'})
        alter_data_search = request.GET.get('alter_data_search')
        if alter_data_search == 'True':  # 将数据库搜索结果返回前端页面
            category = request.GET.get('category')  # 灾难类型
            province = request.GET.get('province')  # 一级行政区
            switch = request.GET.get('switch')  # 筛选开关
            search_list = []  # 搜索结果列表
            search_result = Disaster.objects.filter(
                is_corrected=True)  # 搜索结果

            class Item:  # 结构体
                def __init__(self, title, time, location, category, id, shot):
                    self.title = title
                    self.time = time
                    self.location = location
                    self.category = category
                    self.id = id
                    self.shot = shot
            if switch == 'on':  # 若开启筛选
                search_result = search_result.filter(
                    category=category, province=province).values()  # 筛选搜索结果
            else:
                search_result = search_result.values()
            for sr in search_result:  # 将搜索结果存入结构体对象中并且加入搜索结果列表
                title = sr['title']
                time = sr['time']
                id = str(sr['id'])
                location = sr['location']
                if switch != 'on':
                    category = sr['category']
                filepath = os.path.join(
                    Path(__file__).resolve().parent.parent, 'statics/images/') + id + '.png'
                shot = '暂无'
                if os.path.exists(filepath):
                    shot = '已下载'
                it = Item(title, time, location, category, id, shot)
                search_list.append(it)
            # 将数据返回前端
            return render(request, 'disaster.html', {'func': 'alter_data', 'is_enter': 'False', 'is_search': 'True', 'num': len(search_list), 'search_list': search_list})
        alter_refresh = request.GET.get('alter_refresh')
        if alter_refresh is not None:  # 刷新网页快照
            id = int(alter_refresh)
            url = Disaster.objects.filter(id=id).values()[0]['url']
            threading.Thread(target=save_web_shot,
                             args=(url, alter_refresh)).start()
            return render(request, 'disaster.html', {'func': 'alter_data', 'is_enter': 'False', 'is_search': 'Refresh'})
        alter_delete = request.GET.get('alter_delete')
        if alter_delete is not None:  # 删除灾难事件
            id = int(alter_delete)
            filepath = os.path.join(
                Path(__file__).resolve().parent.parent, 'statics/images/') + alter_delete + '.png'
            if os.path.exists(filepath):  # 删除灾难事件对应的网页快照
                os.remove(filepath)
            Disaster.objects.filter(id=id).delete()
            return render(request, 'disaster.html', {'func': 'alter_data', 'is_enter': 'False', 'is_search': 'Delete'})
        alter = request.GET.get('alter')
        if alter is not None:  # 返回数据至修改数据界面
            id = int(alter)
            disaster = Disaster.objects.filter(id=id).values()[0]
            title = disaster['title']
            time = disaster['time']
            location = disaster['location']
            category = disaster['category']
            text = disaster['text']
            filepath = os.path.join(
                Path(__file__).resolve().parent.parent, 'statics/images/') + alter + '.png'
            is_shot = 'False'
            if os.path.exists(filepath):  # 判断网页快照是否已下载
                is_shot = 'True'
            shot = '/static/images/' + alter + '.png'
            url = disaster['url']
            # 将数据返回前端
            return render(request, 'disaster.html', {'func': 'alter_data', 'is_enter': 'True', 'title': title, 'time': time, 'location': location, 'category': category, 'text': text, 'is_shot': is_shot, 'shot': shot, 'url': url, 'id': id})
        alter_enter = request.GET.get('alter_enter')
        if alter_enter is not None:  # 修改数据并返回修改结果至前端
            id = int(alter_enter)  # 获取前端提交的数据
            title = request.GET.get('title')
            category = request.GET.get('category')
            time = request.GET.get('time')
            province = request.GET.get('province')
            prefecture = request.GET.get('prefecture')
            Disaster.objects.filter(id=id).update(
                title=title, category=category, time=time, province=province, prefecture=prefecture, location=province+prefecture)  # 在数据库中修改数据
            disaster = Disaster.objects.filter(id=id).values()[0]  # 获取前端提交的数据
            title = disaster['title']
            time = disaster['time']
            location = disaster['location']
            category = disaster['category']
            text = disaster['text']
            filepath = os.path.join(
                Path(__file__).resolve().parent.parent, 'statics/images/') + alter_enter + '.png'
            is_shot = 'False'
            if os.path.exists(filepath):
                is_shot = 'True'
            shot = '/static/images/' + alter_enter + '.png'
            url = disaster['url']
            # 返回数据至前端界面
            return render(request, 'disaster.html', {'func': 'alter_data', 'is_enter': 'True', 'title': title, 'time': time, 'location': location, 'category': category, 'text': text, 'is_shot': is_shot, 'shot': shot, 'url': url, 'id': id, 'is_alter_enter': 'True'})
        correct_data_search = request.GET.get('correct_data_search')
        if correct_data_search == 'True':  # 将数据库搜索结果返回前端页面
            category = request.GET.get('category')  # 灾难类型
            switch = request.GET.get('switch')  # 筛选开关
            search_list = []  # 搜索结果列表
            search_result = Disaster.objects.filter(
                is_corrected=False)  # 搜索结果

            class Item:  # 结构体
                def __init__(self, title, time, location, category, id, shot):
                    self.title = title
                    self.time = time
                    self.location = location
                    self.category = category
                    self.id = id
                    self.shot = shot
            if switch == 'on':  # 若开启筛选
                search_result = search_result.filter(
                    category=category).values()  # 筛选搜索结果
            else:
                search_result = search_result.values()
            for sr in search_result:  # 将搜索结果存入结构体对象中并且加入搜索结果列表
                title = sr['title']
                time = sr['time']
                id = str(sr['id'])
                location = sr['location']
                if switch != 'on':
                    category = sr['category']
                filepath = os.path.join(
                    Path(__file__).resolve().parent.parent, 'statics/images/') + id + '.png'
                shot = '暂无'
                if os.path.exists(filepath):
                    shot = '已下载'
                it = Item(title, time, location, category, id, shot)
                search_list.append(it)
            # 将数据返回前端
            return render(request, 'disaster.html', {'func': 'correct_data', 'is_enter': 'False', 'is_search': 'True', 'num': len(search_list), 'search_list': search_list})
        fresh = request.GET.get('fresh')
        if fresh == 'True':  # 刷新数据库
            return render(request, 'disaster.html', {'func': 'correct_data', 'is_enter': 'False', 'is_search': 'Fresh'})
        correct_delete = request.GET.get('correct_delete')
        if correct_delete is not None:  # 删除灾难事件
            id = int(correct_delete)
            filepath = os.path.join(
                Path(__file__).resolve().parent.parent, 'statics/images/') + correct_delete + '.png'
            if os.path.exists(filepath):
                os.remove(filepath)  # 删除灾难事件对应的网页快照
            Disaster.objects.filter(id=id).delete()
            return render(request, 'disaster.html', {'func': 'correct_data', 'is_enter': 'False', 'is_search': 'Delete'})
        correct_refresh = request.GET.get('correct_refresh')
        if correct_refresh is not None:  # 刷新网页快照
            id = int(correct_refresh)
            url = Disaster.objects.filter(id=id).values()[0]['url']
            threading.Thread(target=save_web_shot,
                             args=(url, correct_refresh)).start()
            return render(request, 'disaster.html', {'func': 'correct_data', 'is_enter': 'False', 'is_search': 'Refresh'})
        correct = request.GET.get('correct')
        if correct is not None:  # 返回数据至校正数据界面
            id = int(correct)
            disaster = Disaster.objects.filter(id=id).values()[0]
            title = disaster['title']
            time = disaster['time']
            location = disaster['location']
            category = disaster['category']
            text = disaster['text']
            filepath = os.path.join(
                Path(__file__).resolve().parent.parent, 'statics/images/') + correct + '.png'
            is_shot = 'False'
            if os.path.exists(filepath):  # 判断网页快照是否已下载
                is_shot = 'True'
            shot = '/static/images/' + correct + '.png'
            url = disaster['url']
            # 将数据返回前端
            return render(request, 'disaster.html', {'func': 'correct_data', 'is_enter': 'True', 'is_correct_enter': 'False', 'title': title, 'time': time, 'location': location, 'category': category, 'text': text, 'is_shot': is_shot, 'shot': shot, 'url': url, 'id': id})
        correct_enter = request.GET.get('correct_enter')
        if correct_enter is not None:  # 校正数据并返回校正结果至前端
            id = int(correct_enter)  # 获取前端提交的数据
            title = request.GET.get('title')
            category = request.GET.get('category')
            time = request.GET.get('time')
            province = request.GET.get('province')
            prefecture = request.GET.get('prefecture')
            Disaster.objects.filter(id=id).update(is_corrected=True,
                                                  title=title,
                                                  category=category, time=time, province=province, prefecture=prefecture, location=province+prefecture)  # 在数据库中修改数据
            disaster = Disaster.objects.filter(id=id).values()[0]#获取校正后的数据
            title = disaster['title']
            time = disaster['time']
            location = disaster['location']
            category = disaster['category']
            text = disaster['text']
            filepath = os.path.join(
                Path(__file__).resolve().parent.parent, 'statics/images/') + correct_enter + '.png'
            is_shot = 'False'
            if os.path.exists(filepath):
                is_shot = 'True'
            shot = '/static/images/' + correct_enter + '.png'
            url = disaster['url']
            # 返回数据至前端界面
            return render(request, 'disaster.html', {'func': 'correct_data', 'is_enter': 'True', 'is_correct_enter': 'True', 'title': title, 'time': time, 'location': location, 'category': category, 'text': text, 'is_shot': is_shot, 'shot': shot, 'url': url})
        display = request.GET.get('display')
        if display == 'True':  # 数据可视化展示
            display_category = request.GET.get('display_category')
            if display_category == '时间轴':
                display_list = []

                class Item:  # 结构体
                    def __init__(self, time, location, title):
                        self.time = time
                        self.location = location
                        self.title = title
                search_result = Disaster.objects.filter(
                    is_corrected=True).order_by('time').values()  # 搜索结果
                for sr in search_result:  # 将搜索结果存入结构体对象中并且加入列表
                    time = sr['time']
                    location = sr['location']
                    title = sr['title']
                    it = Item(time, location, title)
                    display_list.append(it)
                # 将数据返回前端
                return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'time', 'num': len(display_list), 'display_list': display_list})
            elif display_category == '地图':
                province_data = {'北京': 0, '天津': 0, '河北': 0, '山西': 0, '内蒙古': 0, '辽宁': 0, '吉林': 0, '黑龙江': 0, '上海': 0, '江苏': 0, '浙江': 0, '安徽': 0, '福建': 0, '江西': 0, '山东': 0, '河南': 0,
                                 '湖北': 0, '湖南': 0, '广东': 0, '广西': 0, '海南': 0, '重庆': 0, '四川': 0, '贵州': 0, '云南': 0, '西藏': 0, '陕西': 0, '甘肃': 0, '青海': 0, '宁夏': 0, '新疆': 0, '台湾': 0, '香港': 0, '澳门': 0}
                for province in province_data:  # 计算各个地区灾难事件数量
                    province_data[province] = Disaster.objects.filter(
                        is_corrected=True, province__contains=province).count()
                # 将数据返回前端
                return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'map', 'province_data': province_data, 'category': '灾难'})
            elif display_category == '灾难类型统计图':
                category_data = []
                categories = ['地震', '水灾', '火灾', '矿难', '爆炸', '空难']

                class Item:  # 结构体
                    def __init__(self, category, num):
                        self.category = category
                        self.num = num
                search_result = Disaster.objects.filter(
                    is_corrected=True)  # 搜索结果
                for category in categories:  # 将搜索结果存入结构体对象中并且加入列表
                    num = search_result.filter(
                        category=category).count()
                    it = Item(category, num)
                    category_data.append(it)
                # 将数据返回前端
                return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'category', 'category_data': sorted(category_data, key=lambda it: it.num), 'province': '全国', 'num': len(search_result.values())})
            elif display_category == '地区统计图':
                province_data = []
                search_result = Disaster.objects.filter(
                    is_corrected=True).values()
                num = len(search_result)
                provinces = set()
                for sr in search_result:
                    provinces.add(sr['province'])
                search_result = Disaster.objects.filter(
                    is_corrected=True)  # 搜索结果

                class Item:  # 结构体
                    def __init__(self, province, num):
                        self.province = province
                        self.num = num
                for province in provinces:  # 将搜索结果存入结构体对象中并且加入列表
                    num = search_result.filter(
                        province=province).count()
                    it = Item(province, num)
                    province_data.append(it)
                china_data = []

                class Item:  # 结构体
                    def __init__(self, province, dz, hl, hz, mk, bz, kn, num):
                        self.province = province
                        self.dz = dz
                        self.hl = hl
                        self.hz = hz
                        self.mk = mk
                        self.bz = bz
                        self.kn = kn
                        self.num = num
                for province in provinces:  # 将搜索结果存入结构体对象中并且加入列表
                    dz = search_result.filter(
                        province=province, category='地震').count()
                    hl = search_result.filter(
                        province=province, category='水灾').count()
                    hz = search_result.filter(
                        province=province, category='火灾').count()
                    mk = search_result.filter(
                        province=province, category='矿难').count()
                    bz = search_result.filter(
                        province=province, category='爆炸').count()
                    kn = search_result.filter(
                        province=province, category='空难').count()
                    num = search_result.filter(
                        province=province).count()
                    it = Item(province, dz, hl, hz, mk, bz, kn, num)
                    china_data.append(it)
                # 将数据返回前端
                return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'province', 'category': '灾难', 'province_data': sorted(province_data, key=lambda it: it.num), 'num': num, 'china_data': sorted(china_data, key=lambda it: it.num), 'len': len(provinces) * 120})
        map_display = request.GET.get('map_display')
        if map_display == 'True':  # 地图展示
            category = request.GET.get('category')
            province_data = {'北京': 0, '天津': 0, '河北': 0, '山西': 0, '内蒙古': 0, '辽宁': 0, '吉林': 0, '黑龙江': 0, '上海': 0, '江苏': 0, '浙江': 0, '安徽': 0, '福建': 0, '江西': 0, '山东': 0, '河南': 0,
                             '湖北': 0, '湖南': 0, '广东': 0, '广西': 0, '海南': 0, '重庆': 0, '四川': 0, '贵州': 0, '云南': 0, '西藏': 0, '陕西': 0, '甘肃': 0, '青海': 0, '宁夏': 0, '新疆': 0, '台湾': 0, '香港': 0, '澳门': 0}
            for province in province_data:
                search_result = Disaster.objects.filter(
                    is_corrected=True, province__contains=province)
                if category != '全部类型':
                    search_result = search_result.filter(category=category)
                province_data[province] = search_result.count()
            return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'map', 'province_data': province_data, 'category': category if category != '全部类型' else '灾难'})
        time_display = request.GET.get('time_display')
        if time_display == 'True':  # 时间轴展示
            category = request.GET.get('category')
            display_list = []

            class Item:
                def __init__(self, time, location, title):
                    self.time = time
                    self.location = location
                    self.title = title
            search_result = Disaster.objects.filter(
                is_corrected=True).order_by('time')
            if category != '全部类型':
                search_result = search_result.filter(category=category)
            search_result = search_result.values()
            for sr in search_result:
                time = sr['time']
                location = sr['location']
                title = sr['title']
                it = Item(time, location, title)
                display_list.append(it)
            return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'time', 'num': len(display_list), 'display_list': display_list})
        display_back = request.GET.get('display_back')
        if display_back == 'True':  # 返回按钮
            return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'main'})
        category_display = request.GET.get('category_display')
        if category_display == 'True':  # 灾难类型统计图展示
            province = request.GET.get('province')
            switch = request.GET.get('switch')
            category_data = []
            categories = ['地震', '水灾', '火灾', '矿难', '爆炸', '空难']
            search_result = Disaster.objects.filter(is_corrected=True)
            if switch == 'on':
                search_result = search_result.filter(province=province)

            class Item:
                def __init__(self, category, num):
                    self.category = category
                    self.num = num
            for category in categories:
                num = search_result.filter(
                    category=category).count()
                it = Item(category, num)
                category_data.append(it)
            return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'category', 'category_data': sorted(category_data, key=lambda it: it.num), 'province': province if switch == 'on' else '全国', 'num': len(search_result.values())})
        province_display = request.GET.get('province_display')
        if province_display == 'True':  # 地区统计图展示
            category = request.GET.get('category')
            province_data = []
            search_result = Disaster.objects.filter(
                is_corrected=True)
            if category != '全部类型':
                search_result = search_result.filter(category=category)
            search_result = search_result.values()
            num = len(search_result)
            provinces = set()
            for sr in search_result:
                provinces.add(sr['province'])
            search_result = Disaster.objects.filter(
                is_corrected=True)
            if category != '全部类型':
                search_result = search_result.filter(category=category)

            class Item:
                def __init__(self, province, num):
                    self.province = province
                    self.num = num
            for province in provinces:
                num = search_result.filter(
                    province=province).count()
                it = Item(province, num)
                province_data.append(it)
            search_result = Disaster.objects.filter(
                is_corrected=True).values()
            provinces = set()
            for sr in search_result:
                provinces.add(sr['province'])
            search_result = Disaster.objects.filter(
                is_corrected=True)
            china_data = []

            class Item:
                def __init__(self, province, dz, hl, hz, mk, bz, kn, num):
                    self.province = province
                    self.dz = dz
                    self.hl = hl
                    self.hz = hz
                    self.mk = mk
                    self.bz = bz
                    self.kn = kn
                    self.num = num
            for province in provinces:
                dz = search_result.filter(
                    province=province, category='地震').count()
                hl = search_result.filter(
                    province=province, category='水灾').count()
                hz = search_result.filter(
                    province=province, category='火灾').count()
                mk = search_result.filter(
                    province=province, category='矿难').count()
                bz = search_result.filter(
                    province=province, category='爆炸').count()
                kn = search_result.filter(
                    province=province, category='空难').count()
                num = search_result.filter(
                    province=province).count()
                it = Item(province, dz, hl, hz, mk, bz, kn, num)
                china_data.append(it)
            return render(request, 'disaster.html', {'func': 'display_data', 'interface': 'province', 'category': category if category != '全部类型' else '灾难', 'province_data': sorted(province_data, key=lambda it: it.num), 'num': num, 'china_data': sorted(china_data, key=lambda it: it.num), 'len': len(provinces) * 120})
        mine = request.GET.get('mine')
        if mine == 'True':  # 数据挖掘
            mining_category = request.GET.get('mining_category')
            if mining_category == '关键词':
                filepath = os.path.join(settings.MEDIA_ROOT, 'txt.txt')
                search_result = Disaster.objects.filter(
                    is_corrected=True).values()
                with open(filepath, 'w', encoding='utf-8') as fp:  # 将文本写入文件
                    for s in search_result:
                        fp.write(s['text']+'\n')
                        fp.write(s['title']+'\n')
                        fp.write(s['category']+' '+s['province'] +
                                 ' '+s['prefecture']+'\n')
                txt = open(filepath, 'r',
                           encoding='utf-8').read()  # 读取文件
                for sw in stop_words:  # 屏蔽停用词
                    txt = txt.replace(sw, '')
                tags = jieba.analyse.extract_tags(
                    txt, topK=100, withWeight=True)  # 挖掘关键词
                text = ''
                s = 100
                for t in tags:
                    for i in range(s):
                        text += t[0] + ' '
                    s -= 1
                if os.path.exists(filepath):  # 删除临时文件
                    os.remove(filepath)
                # 将数据返回前端
                return render(request, 'disaster.html', {'func': 'data_mining', 'interface': 'key', 'text': text, 'category': '灾难'})
            elif mining_category == '主题摘要':
                return render(request, 'disaster.html', {'func': 'data_mining', 'interface': 'abs'})
        mine_back = request.GET.get('mine_back')
        if mine_back == 'True':  # 返回按钮
            return render(request, 'disaster.html', {'func': 'data_mining', 'interface': 'main'})
        key_mining = request.GET.get('key_mining')
        if key_mining == 'True':  # 挖掘关键词
            category = request.GET.get('category')
            filepath = os.path.join(settings.MEDIA_ROOT, 'txt.txt')
            search_result = Disaster.objects.filter(
                is_corrected=True)
            if category != '全部类型':
                search_result = search_result.filter(category=category)
            search_result = search_result.values()
            with open(filepath, 'w', encoding='utf-8') as fp:  # 将文本写入文件
                for s in search_result:
                    fp.write(s['text']+'\n')
                    fp.write(s['title']+'\n')
                    fp.write(s['category']+' '+s['province'] +
                             ' '+s['prefecture']+'\n')
            txt = open(filepath, 'r',
                       encoding='utf-8').read()  # 读取文件
            for sw in stop_words:  # 屏蔽停用词
                txt = txt.replace(sw, '')
            tags = jieba.analyse.extract_tags(
                txt, topK=100, withWeight=True)  # 挖掘关键词
            text = ''
            s = 100
            for t in tags:
                for i in range(s):
                    text += t[0] + ' '
                s -= 1
            if os.path.exists(filepath):  # 删除临时文件
                os.remove(filepath)
            # 将数据返回前端
            return render(request, 'disaster.html', {'func': 'data_mining', 'interface': 'key', 'text': text, 'category': category if category != '全部类型' else '灾难'})
        abs_mining = request.GET.get('abs_mining')
        if abs_mining == 'True':  # 挖掘主题与摘要
            category = request.GET.get('category')  # 灾难类型
            search_result = Disaster.objects.filter(
                is_corrected=True, category=category).values()
            abstract = []  # 主题摘要列表
            pattern = r'\[[^()]*\]'
            for s in search_result:  # 将主题摘要加入列表
                if len(s['text']) > 0:
                    summary = get_summary(
                        re.sub(pattern, '', s['text']), 1)  # 挖掘主题与摘要
                    for i in summary:
                        if len(i) < 150 and len(i) > 20:  # 屏蔽长度不太合理的结果
                            abstract.append(i)
            # 将数据返回前端
            return render(request, 'disaster.html', {'func': 'data_mining', 'interface': 'abs', 'abstract': abstract, 'category': category, 'num': len(abstract)})

        func = request.GET.get('func')
        if func == 'manual_import' or func == 'auto_import':
            return render(request, 'disaster.html', {'func': func})
        elif func == 'alter_data' or func == 'correct_data':
            return render(request, 'disaster.html', {'func': func, 'is_enter': 'False'})
        elif func == 'display_data':
            return render(request, 'disaster.html', {'func': func, 'interface': 'main'})
        elif func == 'data_mining':
            return render(request, 'disaster.html', {'func': func, 'interface': 'main'})
    if request.method == 'POST':
        auto_import = request.FILES.get('auto_import')  # 获取输入的文件
        if auto_import.name.endswith('.txt'):  # 如果是txt文本文件
            lines = auto_import.readlines()
            for line in lines:  # 读取文件每一行的网页地址
                threading.Thread(target=auto_import_data, args=(
                    line.decode().replace('\n', ''),)).start()  # 启动自动导入数据线程
            # 返回正确信息
            return render(request, 'disaster.html', {'func': 'auto_import', 'is_auto_import': 'True'})
        elif auto_import.name.endswith('.csv'):  # 如果是csv表格文件
            filepath = os.path.join(settings.MEDIA_ROOT, auto_import.name)
            with open(filepath, 'wb') as fp:  # 临时保存输入的文件
                for ck in auto_import.chunks():
                    fp.write(ck)
            with open(filepath, 'r', newline='', encoding='utf-8-sig') as csvfile:
                spamreader = csv.reader(csvfile)
                for row in spamreader:  # 读取文件每一行的网页地址
                    threading.Thread(target=auto_import_data,
                                     args=(row[0],)).start()  # 启动自动导入数据线程
            if os.path.exists(filepath):  # 删除临时文件
                os.remove(filepath)
            # 返回正确信息
            return render(request, 'disaster.html', {'func': 'auto_import', 'is_auto_import': 'True'})
        else:
            # 返回错误信息
            return render(request, 'disaster.html', {'func': 'auto_import', 'is_auto_import': 'False'})
    return render(request, 'disaster.html', {'func': 'manual_import'})
