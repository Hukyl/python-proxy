"""
This module provides proxy manager, which searches, tests and delivers proxy.

Classes:
    - Anonimity -> enumeration of proxy anonimity type
    - ProxyManager -> proxy manager
"""

import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Callable

import requests
from bs4 import BeautifulSoup as bs


FILTERS: list[str] = [
    'ALL', 'AU', 'BD', 'BR', 'BY', 'CA', 'CO', 'CZ', 'DE', 'DO', 'EC', 'EG',
    'ES', 'FR', 'GB', 'GR', 'HK', 'ID', 'IL', 'IN', 'IT', 'JP', 'KR', 'MD',
    'MX', 'NL', 'PH', 'PK', 'PL', 'PS', 'RO', 'RU', 'SE', 'SG', 'SY', 'TH',
    'TR', 'TW', 'UA', 'US', 'UZ', 'VE', 'VN', 'YE', 'ZA', 'ZM'
]

class Anonymity(IntEnum):
    """
    Anonimity enumeration
    """
    UNDETECTED = -1
    TRANSPARENT = 0
    ANONYMOUS = 1
    ELITE = 2


V = str | int | bool | Anonymity


class ProxyManager:
    """
    Proxy manager for searching and testing
    """

    AGENT = "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"
    FETCH_URL = "https://free-proxy-list.net/"
    TEST_URL = "https://icanhazip.com/"

    def __init__(self):
        self.session: requests.Session = requests.Session()
        self._anonymity = {
            'transparent': Anonymity.TRANSPARENT,
            'elite proxy': Anonymity.ELITE,
            'anonymous': Anonymity.ANONYMOUS
        }

    def _fetch_data(self) -> list[dict[str, V]]:
        """Fetch list of unchecked unfiltered proxies"""
        response = requests.get(self.FETCH_URL)
        response.raise_for_status()
        rows = bs(response.text, "html.parser").find_all("tr")
        proxies = []
        for row in rows[1:]:
            parts = row.find_all('td')
            if len(parts) != 8:
                continue
            proxies.append({
                'ip': parts[0].text,
                'port': int(parts[1].text),
                'country_code': parts[2].text,
                'anonymity': self._anonymity.get(
                    parts[4].text.lower(), Anonymity.UNDETECTED
                ),
                'is_google': parts[5].text == 'yes',
                'is_https': parts[6].text == 'yes',
                'last_checked': (datetime.utcnow() - timedelta(
                    minutes=int(parts[7].text.split()[0])
                )).replace(microsecond=0)
            })
        return proxies

    def fetch_proxies(
                self, filter_func: Callable = None, /
            ) -> list[dict[str, V]]:
        """
        Fetch list of proxies.
        Data is retrieved through ThreadPoolExecutor, so its testing is
        faster in the long run.

        Args:
            filter_func (Callable, optional): Function to filter proxy.
                Defaults to test by `test_proxy()`.
            limit (int, optional): Limit of proxies. Defaults to None.

        Returns:
            list[dict[str, str | int | bool | Anonymity]]
        """
        filter_func = filter_func or self.test_proxy
        data = self._fetch_data()
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(filter_func(x)) for x in data]
            return [
                proxy for idx, (proxy, is_ok) in enumerate(zip(
                    data, (f.result for f in futures)
                )) if is_ok
            ]

    def cycle(self, filter_func: Callable = None, /) -> dict[str, V]:
        """
        Cycle through proxies. It tests proxies syncronously one-by-one
        so it's faster if you need only several proxies on the spot.

        Args:
            filter_func (Callable, optional).
                By default filters by `ProxyManager.test_proxy()`.

        Yields:
            Iterator[dict[str, str | int | bool | Anonymity]]
        """
        filter_func = filter_func or self.test_proxy
        for data in self._fetch_data():
            if filter_func(data):
                yield data

    @staticmethod
    def format_proxy(proxy: dict[str, V]) -> dict[str, V]:
        """
        Format output of `fetch_proxies()` for individual proxy
            into `requests` module format.

        Args:
            proxy (dict[str, str | int | bool | Anonymity]).
                Proxy dict to be formatted

        Returns:
            dict[str, str | int | bool | Anonymity]
        """
        return {
            "https": f"http://{proxy['ip']}:{proxy['port']}",
            "http": f"http://{proxy['ip']}:{proxy['port']}"
        }

    def test_proxy(
                self, proxy: dict[str, V], /, *, timeout: int = 3
            ) -> bool:
        """
        Test proxy.
        Input proxy format should be the same
            as output of `fetch_proxies()`.

        Args:
            proxy (dict[str, str | int | bool | Anonymity])
            timeout (int): Set max timeout for request response.
                Defaults to 3. Measured in seconds.

        Returns:
            bool: is proxy working or not
        """
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                response = requests.get(
                    self.TEST_URL, headers={'User-Agent': self.AGENT},
                    proxies=self.format_proxy(proxy), verify=False,
                    timeout=timeout
                )
            return response.text.strip() == proxy['ip']
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.ProxyError:
            return False
