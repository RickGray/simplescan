#!/usr/bin/env python
# coding: utf-8

# __buildin__ modules
import os
import re
import sys
import time
import random
import string
import difflib
import urlparse
import argparse

from multiprocessing.dummy import Pool as ThreadPool

# thirdparty modules
import socks
import requests


BANNER = r'''
   _____ _                 __    _____
  / ___/(_)___ ___  ____  / /__ / ___/_________ _____
  \__ \/ / __ `__ \/ __ \/ / _ \\__ \/ ___/ __ `/ __ \
 ___/ / / / / / / / /_/ / /  __/__/ / /__/ /_/ / / / /
/____/_/_/ /_/ /_/ .___/_/\___/____/\___/\__,_/_/ /_/
                /_/

   Author: RickGray@0xFA-Team          |
           Croxy@0xFA-Team             |
   Create: 2015-10-19                  |
   Update: 2015-10-19                  |
  Version: 0.1-alpha                   |
_______________________________________|
'''


_OPTIONS_HELP_ = {
    'URL': 'Target URL (e.g. "http://www.example.com/)',
    'URLFILE': 'Scan multiple targets given in a textual file',
    'WORDFILE': 'Load wordlist from a wordfile (e.g. "wordlist.txt")',
    'WORDFILEDIR': 'Load wordlist from a directory (e.g. "wordlist/")',
    'PROXY': 'Usa a proxy to connect to the target URL',
    'AGENT': 'HTTP User-Agent header value',
    'COOKIE': 'HTTP Cookie header value',
    'TIMEOUT': 'Seconds to wait before timeout connection (default 10)',
    'THREADS': 'Max number of concurrent HTTP(s) requests (default 10)',
}


def parse_commond():
    """ 解析终端命令并返回其解析结果 """
    parse = argparse.ArgumentParser()

    target = parse.add_argument_group('target')
    target.add_argument('-u', dest='URL',
                        type=str, help=_OPTIONS_HELP_['URL'])
    target.add_argument('-f', dest='URLFILE',
                        type=str, help=_OPTIONS_HELP_['URLFILE'])

    wordfile = parse.add_argument_group('wordfile')
    wordfile.add_argument('-w', dest='WORDFILE',
                          type=str, help=_OPTIONS_HELP_['WORDFILE'])
    wordfile.add_argument('-d', dest='WORDFILEDIR',
                          type=str, help=_OPTIONS_HELP_['WORDFILEDIR'])

    request = parse.add_argument_group('request')
    request.add_argument('--proxy', dest='PROXY',
                         type=str, help=_OPTIONS_HELP_['PROXY'])
    request.add_argument('--user-agent', dest='AGENT',
                         type=str, help=_OPTIONS_HELP_['AGENT'])
    request.add_argument('--cookie', dest='COOKIE',
                         type=str, help=_OPTIONS_HELP_['COOKIE'])
    request.add_argument('--timeout', dest='TIMEOUT',
                         type=int, default=10, help=_OPTIONS_HELP_['TIMEOUT'])

    optimization = parse.add_argument_group('optimization')
    optimization.add_argument('--threads', dest='THREADS',
                              type=int, default=10, help=_OPTIONS_HELP_['THREADS'])

    return parse.parse_args()


def get_random_string(length=16):
    """ 随机生成指定长度由大小写字母和数字构成的字符串 """
    choices = string.letters + string.digits
    return ''.join([random.choice(choices) for _ in range(int(length))])


def build_random_path():
    """ 随机生成由大小写字母和数字构成的路径 """
    random_string = get_random_string(random.randint(5, 10))
    ext_choices = ['.html', '.php', '.asp', '.htm', '.jpeg', '.png', '.zip']
    random_path = random_string
    while True:
        # 随机构建子路径，当 random.choice([True, False]) 为 False 时退出循环
        if not random.choice([True, False]):
            random_path += random.choice(ext_choices)
            break
        else:
            random_string = get_random_string(random.randint(5, 10))
            random_path += '/' + random_string

    return random_path


def patch_url(url):
    """ 修复不标准URL """
    res = urlparse.urlparse(url)
    if not res.scheme:
        url = 'http://' + url

    return url


def build_not_found_template(url):
    """ 获取扫描URL基本路径，构建基于当前目录的404页面模板 """
    base_url = urlparse.urljoin(url, './')

    pre_responses = []
    for _ in range(6):
        # 随机生成路径，相继访问得到页面内容，对成功返回的结果进行比较得到404页面模板
        random_path = build_random_path()
        random_url = urlparse.urljoin(base_url, random_path)
        try:
            response = requests.get(random_url)
        except requests.exceptions.RequestException, ex:
            err = 'failed to access %s, ' % random_url
            err += str(ex)
            print err
            continue
        pre_responses.append(response)

    if len(pre_responses) < 2:
        # 由于随机获取到的页面内容数量太少不能进行 404页面模板 提取操作
        return None

    ratios = []
    pre_content = pre_responses[0].content
    for response in pre_responses[1:]:
        cur_content = response.content
        ratio = difflib.SequenceMatcher(None, pre_content, cur_content).quick_ratio()
        ratios.append(ratio)
        pre_content = cur_content

    average = float(sum(ratios)) / len(ratios)
    if average > 0.9:
        print 'succeed to build %s 404 page template' % url

    return random.choice(pre_responses).content


# def check_url(url, err_content):
def check_url(opt):
    """ 请求指定URL地址，返回其状态值，根据 err_content 来过滤404页面 """
    url, err_content = opt[0], opt[1]
    try:
        response = requests.get(url, stream=True)
    except requests.exceptions.RequestException, ex:
        err = 'failed to access %s, ' % url
        err += str(ex)
        return None

    if err_content:
        content = response.content
        ratio = difflib.SequenceMatcher(None, content, err_content).quick_ratio()
        if ratio > 0.9:
            # print 'fetched similar page or others'
            return None

    status_code = response.status_code
    m = re.search(r'<title>(?P<title>.*)</title>', response.content)
    page_title = m.group('title') if m else ''
    sys.stdout.write('[{0}], [{1}], [{2}]\n'.format(status_code, page_title, url))
    return status_code, page_title


def set_request_proxy(proxy):
    """ 设置请求代理 """
    res = urlparse.urlparse(proxy)
    mode = None
    if res.scheme == 'socks4':
        mode = socks.SOCKS4
    elif res.scheme == 'socks5':
        mode = socks.SOCKS5
    elif res.scheme == 'http':
        mode = socks.HTTP
    else:
        print 'unknown proxy type'

    if mode:
        host = res.netloc.split(':')[0]
        port = int(res.netloc.split(':')[1])
        socks.set_default_proxy(mode, host, port)
        socks.socket = socks.socksocket
        print 'proxy %s using' % proxy


def build_extended_wordlist(t_url):
    """ 根据待扫描域名和URL生成基本扫描字典 """
    wordlist = []

    return wordlist


def process_with_url(url, args):
    """ 单一目标扫描处理 """
    t_url = patch_url(url)
    if not args.WORDFILE and not args.WORDFILEDIR:
        print 'wordfile or wordfile dir required'
        sys.exit()

    try:
        w_fd = open(args.WORDFILE, 'r')
    except IOError, ex:
        err = 'unable to load wordfile, ("%s")' % str(ex)
        print err
        sys.exit()

    # 获取 404页面模板
    err_content = build_not_found_template(t_url)
    # TODO 需要改进多线程参数冗余 - err_content
    # 在生成带扫描URL时，默认以当前目录为扫描路径
    l = [(urlparse.urljoin(t_url, _.strip().lstrip('/')), err_content)
         for _ in build_extended_wordlist(t_url)]
    l += [(urlparse.urljoin(t_url, _.strip().lstrip('/')), err_content)
          for _ in w_fd.readlines()]

    # 初始化线程池
    # TODO 需要定义线程函数回调 callback，用于收集结果给外部程序使用
    pool = ThreadPool(args.THREADS)
    pool.map(check_url, l)


def process_with_url_file(url_file, args):
    """ 目标文件扫描处理 """
    try:
        u_fd = open(url_file, 'r')
    except IOError, ex:
        err = 'unable to load url file, ("%s")' % str(ex)
        print err
        sys.exit()

    while True:
        try:
            url = u_fd.next().strip()
        except StopIteration, ex:
            print 'no more url found, ("%s")' % str(ex)
            break

        # TODO 定义输出接口数据格式
        process_with_url(url, args)


def run(args):
    print BANNER
    # TODO 全局中断信号处理，用于多线程运行时立即退出程序

    if args.PROXY:
        set_request_proxy(args.PROXY)

    if not args.URL and not args.URLFILE:
        print 'url or url file required'
        sys.exit()

    if args.URL:
        return process_with_url(args.URL, args)
    if args.URLFILE:
        return process_with_url_file(args.URLFILE, args)


if __name__ == '__main__':
    run(parse_commond())
