import json
import os
from multiprocessing import dummy
from itertools import islice
import requests
from time import sleep
import newspaper
from helpers import timeit, LemmaTokenizer
from plotter import plot

nlp_api = 'https://lbs45qdjea.execute-api.us-west-2.amazonaws.com/prod/newscraper-dev'
scrape_api = 'https://x9wg9drtci.execute-api.us-west-2.amazonaws.com/prod/article_get'
import textblob
analyzer = textblob.sentiments.PatternAnalyzer().analyze


class LambdaWhisperer:
    json_results = []

    def __init__(self):
        pass

    @timeit
    def scrape_api_endpoint(self, text_):
        response = json.loads(requests.put(scrape_api, data=text_).text)
        sleep(.1)
        if 'message' in response:
            return None

        return response

    @timeit
    def nlp_api_endpoint(self, text_):
        response = json.loads(requests.put(nlp_api, data=text_).text)
        LambdaWhisperer.json_results = [response]

        return response

    @timeit
    def send(self, articles):

        cleaned = ' '.join(LemmaTokenizer(articles))

        self.snoop(cleaned)
        return self.nlp_api_endpoint(cleaned)

    def snoop(self, cleaned):
        from collections import Counter
        c = Counter(cleaned.split(' '))
        print(c.most_common(15))


class Titles:
    collect = []


class GetSite:

    def __init__(self, url, name_clean=None, limit=20):
        self.API = LambdaWhisperer()
        self.limit = limit
        self.url = self.https_test(url)
        if not name_clean:
            self.name_clean = self.strip()
        else:
            self.name_clean = name_clean
        # if os.path.exists(self.name_clean + '.txt'):
        #     os.remove(self.name_clean + '.txt')

    def run(self):
        if not self.url:
            return False
        # Get list of newspaper.Article objs
        self.article_objs = self.get_newspaper()

        # Threadpool for getting articles

        self.article_objs = islice(self.article_objs, self.limit * 2)
        self.articles = self.articles_gen()

        self.API.send(self.articles)

        if self.API.json_results:
            self.dump()
            self.save_plot()

        polarity, subjectivity = analyzer(self.articles)
        return self.num_articles, round(polarity, 3), round(subjectivity, 3)

    def save_plot(self):
        plot(url=self.url, name_clean=self.name_clean)

    @timeit
    def articles_gen(self):

        url_list = [a.url for a in self.article_objs]
        res1 = list(dummy.Pool(40).imap_unordered(self.API.scrape_api_endpoint, url_list[:self.limit]))
        sleep(1)
        res2 = list(dummy.Pool(40).imap_unordered(self.API.scrape_api_endpoint, url_list[:self.limit]))
        res = res1 + res2
        res = [_ for _ in res if _ is not None]
        self.num_articles = len(res)

        return ' '.join(res)

    def strip(self):
        return ''.join([
            c for c in self.url.replace('https://', '').replace('http://', '').replace('www.', '')
            if c.isalpha()
        ])

    def dump(self):

        j_path = './static/{}.json'.format(self.name_clean)
        with open(j_path, 'w') as fp:
            json.dump(LambdaWhisperer.json_results, fp, sort_keys=True)

    @timeit
    def test_url(self, url_):
        try:
            if requests.get(url_, timeout=(1, 1)).ok:
                return url_
            else:
                return False
        except requests.exceptions.ConnectionError:
            return False

    @timeit
    def https_test(self, url):
        if 'http://' or 'https://' not in url:
            url = self.test_url('https://' + url) or self.test_url('http://' + url)
            print(url)
            if not url:
                print('No website here!')
                return
            return url

    @timeit
    def get_newspaper(self):

        try:
            src = newspaper.build(
                self.url,
                fetch_images=False,
                request_timeout=2,
                limit=self.limit,
                memoize_articles=False)

        except Exception as e:
            print(e)
            print(self.url)
            return "No articles found!"
        print(len(src.articles))
        print(src.articles[0].url)

        return src.articles

    def get_articles(self, url):

        try:
            article = newspaper.Article(url)
            article.download()
            article.parse()

        except newspaper.article.ArticleException:
            return ''
        # with open('static/{}.txt'.format(self.name_clean), 'a+') as log:
        #     log.write(article.title)
        #     print('static/{}.txt'.format(self.name_clean))

        return article.text + ' ' + article.title


# if __name__ == '__main__':

#     @timeit
#     def run(url, sample_articles=None):
#         GetSite(url, sample_articles).run()
#         print(sorted(LambdaWhisperer.json_results[0].items(), key=lambda kv: kv[1]))
