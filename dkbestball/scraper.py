import logging

import browser_cookie3
from requests_html import HTMLSession


class Scraper:
    """Scrape DK site for data"""

    def __init__(self):
        logging.getLogger(__file__).addHandler(logging.NullHandler())
        self.s = HTMLSession()
        self.s.headers.update({
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)',
            'DNT': '1',
            'Accept': '*/*',
            'Origin': 'https://www.draftkings.com',
            'Sec-Fetch-Site': 'same-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://www.draftkings.com/',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
        })
        self.cj = browser_cookie3.firefox()

    @property
    def api_url(self):
        return 'https://api.draftkings.com/'

    @property
    def base_params(self):
        return {'format': 'json'}

    def _embed_params(self, embed_type):
        return dict(**self.base_params, **{'embed': embed_type})

    def contest_leaderboard(self, contest_id):
        """Gets contest leaderboard"""
        url = self.api_url + f'scores/v1/megacontests/{contest_id}/leaderboard'
        params = self._embed_params('leaderboard')
        return self.get_json(url, params=params)

    def contest_roster(self, draftgroup_id, entry_key):
        """Gets contest roster"""
        url = self.api_url + f'scores/v2/entries/{draftgroup_id}/{entry_key}'
        params = self._embed_params('roster')
        return self.get_json(url, params=params)

    def get_json(self, url, params, headers=None, response_object=False):
        """Gets json resource"""
        headers = headers if headers else {}
        r = self.s.get(url, params=params, headers=headers, cookies=self.cj)
        if response_object:
            return r
        return r.json()


if __name__ == '__main__':
    pass
