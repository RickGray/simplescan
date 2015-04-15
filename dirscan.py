#!/usr/bin/env python
# coding: utf-8
# Author: rickchen.vip@gmail.com
#

import sys
import socks
import socket
import platform
import urlparse
import argparse
import requests

from multiprocessing.dummy import Pool as ThreadPool


def cprint(val, color):
    colorcodes = {'bold': {True: '\x1b[1m', False: '\x1b[22m'},
                  'cyan': {True: '\x1b[36m', False: '\x1b[39m'},
                  'blue': {True: '\x1b[34m', False: '\x1b[39m'},
                  'red': {True: '\x1b[31m', False: '\x1b[39m'},
                  'magenta': {True: '\x1b[35m', False: '\x1b[39m'},
                  'green': {True: '\x1b[32m', False: '\x1b[39m'},
                  'yellow': {True: '\x1b[33m', False: '\x1b[39m'},
                  'underline': {True: '\x1b[4m', False: '\x1b[24m'}}
    colors = (platform.system() != 'Windows')
    if colors:
        print colorcodes[color][True] + val + colorcodes[color][False]
    else:
        print val


def getStatus(url):
    try:
        resp = requests.get(url, allow_redirects=False, timeout=30)
        status = resp.status_code
    except requests.Timeout:
        status = 404
    except Exception, e:
        status = 404

    return status


def urlRequest(url):
    global index
    index += 1
    status = getStatus(url)
    if status == 302 or status == 200 or status == 403:
        if status == 200:
            cprint('[+] %s [200 OK]' % url, 'green')
        elif status == 302:
            cprint('[!] %s [302 REDIRECT]' % url, 'yellow')
        elif status == 403:
            cprint('[!] %s [403 FORBIDEN]' % url, 'red')


def parse_argv():
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--proxy', dest='PROXY', type=str,
                        help='Use a proxy to connect target (support: http, socks4, socks5)')
    parser.add_argument('-r', '--offset', dest='OFFSET', type=int,
                        help='Set starting offset in wordlist')
    #parser.add_argument('-o', '--outfile', dest='OUTFILE', type=str)
    parser.add_argument('-t', '--threads', dest='THREADS', type=int, default=10,
                        help='The number of threads')
    #parser.add_argument('--igore', dest='IGNORE', type=str,
    #                    help='Ingore status code if you want (e.g. --ignore=302,403)')

    parser.add_argument('url', type=str, help='Target')
    parser.add_argument('wordlist', type=str, help='The wordlist of something')

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_argv()

    target = args.url
    wordlist = args.wordlist
    offset = 0 if not args.OFFSET else args.OFFSET
    threads = args.THREADS
    proxy = args.PROXY

    if proxy:
        res = urlparse.urlparse(proxy)
        use_proxy = True
        if res.scheme == 'socks4':
            socks.set_default_proxy(socks.SOCKS4, res.netloc.split(':')[0], int(res.netloc.split(':')[1]))
        elif res.scheme == 'socks5':
            socks.set_default_proxy(socks.SOCKS5, res.netloc.split(':')[0], int(res.netloc.split(':')[1]))
        elif res.scheme == 'http':
            socks.set_default_proxy(socks.HTTP, res.netloc.split(':')[0], int(res.netloc.split(':')[1]))
        else:
            use_proxy = False
            cprint('[!] Unknown proxy "%s", starting without proxy...' % proxy, 'bold')

        if use_proxy:
            socket.socket = socks.socksocket

    urls = []
    index = 0
    with open(wordlist) as f:
        while True:
            try:
                path = f.next().strip()
                if index >= offset:
                    urls.append(urlparse.urljoin(target, path))
                    #urls.append(target + path)

                index += 1
            except StopIteration:
                break

    if offset > 0:
        cprint('[+] Resuming search with offset: %d' % offset, 'bold')
    index = 0
    """
    try:
        for url in urls:
            urlRequest(url)
    except KeyboardInterrupt:
        cprint('[*] Interrupted Current Offset: %d' % index, 'red')
        sys.exit()
    """
    try:
        pool = ThreadPool(threads)
        pool.map_async(urlRequest, urls).get(9999999)  # useful for KeyboardInterrupt
    except KeyboardInterrupt:
        cprint('[*] Interrupted Current Offset: %d' % index, 'bold')
        sys.exit()
