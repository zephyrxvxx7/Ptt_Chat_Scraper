import json
import requests
import argparse
from time import sleep
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from six import u
import re
import logging

class ptt_scraper():
    main_url = "https://www.ptt.cc/bbs/"
    root_url = "https://www.ptt.cc"
    over18_payload = {
        'from': 'bbs/Gossiping/index.html', 
        'yes': 'yes'
    }

    def __init__(self):
        self.session = requests.session()
        requests.packages.urllib3.disable_warnings()

        # 載入cookie以達到點選'我已滿18歲'按鈕
        self.session.post("https://www.ptt.cc/ask/over18",
                          verify=False,
                          data=self.over18_payload)
        logging.basicConfig(level=logging.INFO)

    def scraper(self, board="Gossiping", start=38900, end=38900, sleep_time = 0.5):
        page_count = start
        filename = board + str(start) + "-" + str(end)
        
        # 開檔並寫入json第一個符號
        self._output(filename, 'w', '[')
        for page in self._pages(board, int(start), int(end)):
            
            logging.info('parse page url: ' + str(page))

            try:
                for article in self._articles(page):
                    #print('parse article url:', article)
                    self._json_output(filename, 'a', self._parse_article(article))
                    sleep(sleep_time)
            except Exception as e:
                logging.error('在分析{0}頁時發生錯誤, 嘗試繼續執行'.format(page_count))
                logging.error(e)
            
            page_count += 1
        
        # 移動檔案游標並且刪掉
        with open(filename + ".json", mode= 'rb+') as op:
            op.seek(-1, 2)
            op.truncate()
        
        self._output(filename, 'a', ']')
            
    '''
    爬取每個主page
    '''
    def _pages(self, board, start, end):
        for page_range in range(start, end + 1):
            yield self.main_url + board + "/index" + str(page_range) + ".html"
    
    '''
    爬取每篇文章
    '''
    def _articles(self, page):
        soup = BeautifulSoup(self._get_html(page), "lxml")
        divs = soup.find_all('div', 'r-ent')
        for div in divs:
            if div.find('a'):
                # 文章標題
                # print(div.find('a').string)
                yield div.find('a')['href']

    '''
    分析每篇文章
    '''
    def _parse_article(self, url):
        soup = BeautifulSoup(self._get_html(
            self.root_url + url), 'html.parser')
        try:
            article = {}

            # 取得文章作者與文章標題
            article["Author"] = soup.select(".article-meta-value")[0].contents[0].split(" ")[0]
            article["Title"] = re.sub('　', ' ', soup.select(".article-meta-value")[2].contents[0])
            
            # 取得內文並且去除掉部分可能造成錯誤的內容
            content = ""
            main_content = soup.select("#main-content")[0]
            for meta in main_content.select('div.article-metaline'):
                meta.extract()
            for meta in main_content.select('div.article-metaline-right'):
                meta.extract()
            pushes = soup.select(".push")
            for push in main_content.find_all('div', class_='push'):
                push.extract()
            
            # 移除 '※ 發信站:' (starts with u'\u203b'), '◆ From:' (starts with u'\u25c6'), 空行及多餘空白
            # 保留英數字, 中文及中文標點, 網址, 部分特殊符號
            filtered = [v for v in main_content.stripped_strings if v[0]
                        not in [u'※', u'◆']]
            
            #去掉'--'後續的字串
            counter = 0
            for filtere in filtered:
                if filtere[:2] == u'--':
	                break
                counter += 1
            filtered = filtered[:counter]
            
            expr = re.compile(
                u(r'[^\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b\s\w:/-_.?~%()]'))
            for i in range(len(filtered)):
                filtered[i] = re.sub(expr, '', filtered[i])

            # 刪除空字串
            filtered = [_f for _f in filtered if _f]
            # 刪掉最後一行有網址的文字
            filtered = [x for x in filtered if url not in x]
            filtered = [x for x in filtered if "http" not in x]
            content = ' '.join(filtered)
            content = re.sub(r'(\s)+', ' ', content)
            article["Content"] = content
            
            # 處理回文資訊
            upvote = 0
            downvote = 0
            novote = 0
            response_list = []

            for response_struct in pushes:

                #跳脫「檔案過大！部分文章無法顯示」的 push class
                if "warning-box" not in response_struct['class']:

                    response_dic = {}
                    response_dic["Content"] = response_struct.select(
                        ".push-content")[0].contents[0][1:]
                    response_dic["Vote"] = response_struct.select(
                        ".push-tag")[0].contents[0][0]
                    response_dic["User"] = response_struct.select(
                        ".push-userid")[0].contents[0]
                    response_list.append(response_dic)

                    if response_dic["Vote"] == u"推":
                        upvote += 1
                    elif response_dic["Vote"] == u"噓":
                        downvote += 1
                    else:
                        novote += 1

            article["Responses"] = response_list
            article["UpVote"] = upvote
            article["DownVote"] = downvote
            article["NoVote"] = novote

        except Exception as e:
            print('*** 在分析{0}的時候發生錯誤 ***'.format(self.root_url + url))
            print(e)

        return article
    
    def _output(self, filename, mode, data):
        with open(filename + ".json", mode=mode, encoding='utf-8') as op:
            op.write(data)
    
    def _json_output(self, filename, mode, data):
        with open(filename + ".json", mode = mode, encoding='utf-8') as op:
            op.write(json.dumps(data, indent=4, ensure_ascii=False))
            op.write(',')
        
    def _get_html(self, object):
        return self.session.get(object).text

if __name__ == "__main__":
    board = "Gossiping"
    start = 38900
    end = 38900
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''
            A crawler for the web version of ptt.cc
            Input: board name and page indices
            Output: BOARD_NAME-START_INDEX-END_INDEX.json
        ''')
    parser.add_argument('-b', metavar='BOARD_NAME',
                        help='Board name', required=True)
    parser.add_argument('-i', metavar=('START_INDEX', 'END_INDEX'),
                        type=int, nargs=2, help="Start and end index", required=True)
    parser.add_argument('-t', metavar='DELAY_TIME',
                        type=float, help="Delay of time(sec.)", default=0.5)
    args = parser.parse_args()

    scraper = ptt_scraper()
    scraper.scraper(board=args.b, start=args.i[0], end=args.i[-1], sleep_time=args.t)
    print('Mission completed!')
    
