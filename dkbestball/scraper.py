import logging
import time

import browser_cookie3
from requests_html import HTMLSession


class Scraper:
    """Scrape DK site for data"""

    def __init__(self, browser_name='firefox'):
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

        if browser_name == 'firefox':
            self.s.cookies.update(browser_cookie3.firefox())
        else:
            raise ValueError('Only firefox cookies are supported at this time')
        
    @property
    def api_url(self):
        return 'https://api.draftkings.com/'

    @property
    def base_params(self):
        return {'format': 'json'}

    def _embed_params(self, embed_type):
        return dict(**self.base_params, **{'embed': embed_type})

    def contest_leaderboard(self, contest_id):
        """Gets contest leaderboard
           For week 1, MegaContestId = ContestId. Week 2+ have unique ContestId.
        
        Args:
            contest_id (int): the ContestId

        Returns:
            dict

        """
        url = self.api_url + f'scores/v1/leaderboards/{contest_id}'
        params = self._embed_params('leaderboard')
        return self.get_json(url, params=params)

    def contest_roster(self, draftgroup_id, entry_key):
        """Gets contest roster
        
        Args:
            draftgroup_id (int): the DraftGroupId, e.g. 37605
            entry_key (int): the ID of the user's entry into the contest

        Returns:
            dict

        """
        url = self.api_url + f'scores/v2/entries/{draftgroup_id}/{entry_key}'
        params = self._embed_params('roster')
        return self.get_json(url, params=params)

    def get_json(self, url, params=None, headers=None, cookies=None):
        """Gets json resource
        
        Args:
            url (str): the resource URL
            headers (dict): one-time headers for the request
            cookies (CookieJar): one-time cookie jar

        """
        r = self.s.get(url, params=params, headers=headers, cookies=cookies)
        return r.json()

    def megacontest_leaderboard(self, megacontest_id):
        """Gets megacontest leaderboard (overall leaderboard)
        
        Args:
            megacontest_id (int): the MegaContestId

        Returns:
            dict

        """
        url = self.api_url + f'scores/v1/megacontests/{megacontest_id}/leaderboard'
        params = self._embed_params('leaderboard')
        return self.get_json(url, params=params)

    def megacontest_entered(self, megacontest_id, userkey):
        """Gets megacontest data (including associated weekly contests)
        
        Args:
            megacontest_id (int): the MegaContestId
            userkey (str): the userkey, is GUID (36 character with dashes)

        Returns:
            dict

        """
        url = self.api_url + f'scores/v1/contest/entered/{userkey}/megacontest/{megacontest_id}'
        params = self.base_params
        return self.get_json(url, params=params)

    def mycontests(self):
        """Gets mycontest resource
           Does not load immediately, so have to request twice after short delay
        """
        url = 'https://www.draftkings.com/mycontests'
        _ = self.s.get(url)
        time.sleep(1)
        return self.s.get(url).text


if __name__ == '__main__':
    pass
