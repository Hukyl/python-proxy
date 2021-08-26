from collections.abc import Iterable
import warnings
from datetime import timedelta

from bs4 import BeautifulSoup as bs
import requests


FILTERS = [
    'ALL', 'AU', 'BD', 'BR', 'BY', 'CA', 'CO', 'CZ', 'DE', 'DO', 'EC', 'EG', 
    'ES', 'FR', 'GB', 'GR', 'HK', 'ID', 'IL', 'IN', 'IT', 'JP', 'KR', 'MD', 
    'MX', 'NL', 'PH', 'PK', 'PL', 'PS', 'RO', 'RU', 'SE', 'SG', 'SY', 'TH', 
    'TR', 'TW', 'UA', 'US', 'UZ', 'VE', 'VN', 'YE', 'ZA', 'ZM'
]


class Proxy(object):
    AGENT = "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"
    FETCH_URL = "https://free-proxy-list.net/"
    TEST_URL = "https://2ip.ru/"

    def __init__(self, *, country_filters: list[str]=[FILTERS[0]]):
        assert country_filters and all(
            x.upper() in FILTERS for x in country_filters
        )
        self.country_filters = [x.upper() for x in country_filters]
        self.session = requests.Session()

    # allows the user to cycle through proxies
    def cycle(self):
        while True:
            for proxy in self.fetch_proxies():
                if self.test_proxy(proxy):
                    yield proxy  
                else:
                    print('Invalid proxy, skipping...')    

    def fetch_proxies(self):
        response = requests.get(self.FETCH_URL)
        response.raise_for_status()
        soup = bs(response.content, "html.parser")
        rows = soup.find_all("tr")
        proxies = []
        for row in rows:
            parts = row.find_all("td")
            if len(parts) == 8:
                ip = parts[0].text
                port = int(parts[1].text)
                country_code = parts[2].text
                country = parts[3].text
                anonymity = parts[4].text
                is_google = parts[5].text == 'yes'
                is_https = parts[6].text == 'yes'
                last_checked = timedelta(
                    minutes=int(parts[7].text.split()[0])
                )
                if is_https and country_code in self.country_filters:
                    proxies.append({
                        'ip': ip, 'port': port, 
                        'country_code': country_code, 'country': country, 
                        'anonymity': anonymity, 'is_google': is_google, 
                        'is_https': is_https, 'last_checked': last_checked
                    })
        return proxies

    @staticmethod
    def format_proxy(proxy):
        return {"https": f"http://{proxy['ip']}:{proxy['port']}"}

    @staticmethod
    def unformat_proxy(proxy: dict):
        ip, port = proxy['http'].lstrip("http://").split(':')
        return (ip, int(port))

    def test_proxy(self, proxy_: dict):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                requests.get(
                    self.TEST_URL, headers={'User-Agent': self.AGENT}, 
                    proxies=self.format_proxy(proxy_), verify=False,
                    timeout=5
                )
            return True
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.ProxyError:
            return False
