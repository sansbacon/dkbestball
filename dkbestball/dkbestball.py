import datetime
import json
import logging
import os
from pathlib import Path
import re
import pytz
import time

import numpy as np
import pandas as pd
from requests_html import HTMLSession
import browser_cookie3


class Scraper:
    """Scrape DK site for data"""

    def __init__(self, user_id=None):
        logging.getLogger(__file__).addHandler(logging.NullHandler())
        if not user_id:
            self.user_id = os.getenv('DK_USER_ID')
        self.s = HTMLSession()
        self.s.headers.update({
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36',
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
        try:
            return r.json()
        except:
            return r.content()


class Parser:
    """
    >>> p = Parser()

    STEP ONE: get list of bestball contests (mycontests)
    https://www.draftkings.com/mycontests

    var contests has the contest information under 'live' (in-season at least)
    view source and then copy to file mycontests.html - can't save directly
    can also just copy and paste variable and then load file directly
    the variable isn't true json, as the keys are not quoted properly
    have maxentrantsperpage, live, upcoming, history
    
    >>> mycontestsfile = Path.home() / 'workspace' / 'dkbestball' / 'tests' / 'mycontests.html'
    >>> mycontests = p.mycontests(mycontestsfile)

    STEP TWO: extract relevant data from mycontests
    so for each contest in mycontests, call contest_details
    create dict of dicts with key = ContestId

    >>> contest_details_dict = {c['ContestId']: p.contest_details(c) for c in mycontests}
     
    STEP THREE: get playerpool
    for 2020, have draftgroup of 37604 or 37605
    can get playerpool for both to match up with contests

    >>> pool = {id: p.player_pool(id=id) for id in (37604, 37605)}

    STEP FOUR: get contest standings (DK calls these leaderboards)
    >>> lb = []
    ... for pth in p.LEADERBOARD_DIR.glob('*.json'):
    ...     data = p._to_obj(pth)
    ...     lb += p.contest_leaderboard(data)

    STEP FIVE: get contest rosters
    >>> rosters = []
    ... for pth in p.ROSTER_DIR.glob('*.json'):
    ...     data = p._to_obj(pth)
    ...     playerd = p.player_pool_dict(id=data['entries'][0]['draftGroupId'])
    ...     rosters += p.contest_roster(data, playerd)

    STEP SIX: match contest details to rosters
    Create a dict of contestkey: contest size
    >>> sized = {item['ContestId']: item['MaxNumberPlayers'] for item in contest_details_dict.values()}
    ... for roster in rosters:
    ...     contest_key = int(roster['contestKey'])
    ...     roster['MaxNumberPlayers'] = sized.get(contest_key)    
    """
    DATADIR = Path(__file__).parent / 'data'
    LEADERBOARD_DIR = DATADIR / 'leaderboards'
    ROSTER_DIR = DATADIR / 'rosters'
    PLAYERPOOL_FIELDS = ['draftableId', 'playerId', 'playerDkId',
                         'displayName', 'position', 'teamAbbreviation']
       

    def __init__(self):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.bestball_gametype_id = 145

    @staticmethod
    def _pctcol(val):
        return f'{round(val * 100, 2)}%'
        
    def _contest_type(self, contest):
        """Determines if tournament or sit_and_go"""
        return 'tournament' if 'Tournament' in contest['ContestName'] else 'sit_and_go'

    def _draftablesfn(self, id):
        return self.DATADIR / f'draftables_{id}.json'

    def _to_dataframe(self, container):
        """Converts container to dataframe"""
        return pd.DataFrame(container)

    def _to_obj(self, pth):
        """Reads json text in pth and creates python object"""
        if isinstance(pth, str):
            pth = Path(pth)
        return json.loads(pth.read_text())

    def contest_details(self, contest):
        """Parses contest dict for relevant details
           Some overlap with leaderboards re: contest leader (UsernameOpp, TotalPointsOpp) 
           and your entry (UserContestId, ResultsRank, PlayerPoints)

        Args:
            content (dict): single contest dict

        Returns:
            dict with keys from wanted, values from content
        """
        wanted = [
            'ContestId',
            'ContestName',
            'BuyInAmount',
            'MaxNumberPlayers',
            'DraftGroupId',
            'GameTypeId',
            'TopPayout',
            'UserContestId',
            'ResultsRank',
            'TotalPointsOpp',
            'UsernameOpp',
            'PlayerPoints'
        ]

        d = {k:contest.get(k) for k in wanted}
        d['ContestType'] = self._contest_type(contest)
        d['ClockType'] = 'slow' if 'Slow Draft' in contest['ContestName'] else 'fast'
        return d

    def contest_leaderboard(self, content):
        """Parses contest leaderboard

        Args:
            content (dict): leaderboard dict

        Returns:
            list: of dict
        """
        vals = []
        wanted = ['userName', 'userKey', 'rank', 'fantasyPoints']
        for item in content['leaderBoard']:
            d = {k:item.get(k) for k in wanted}
            d['contestKey'] = content['contestKey']
            vals.append(d)
        return vals

    def contest_roster(self, content, playerd=None):
        """Parses roster from single contest. DK doesn't seem to have saved draft order.

        Args:
            content (dict): parsed draft resource
            playerd (dict): additional player data
        
        Returns:
            list: of dict
        
        TODO: add stats and utilizations
        """
        entry = content['entries'][0]
        wanted_metadata = ['draftGroupId', 'contestKey', 'entryKey', 'lineupId', 'userName', 'userKey']
        wanted_scorecard = ['displayName', 'draftableId']
        draft_metadata = {k:entry.get(k) for k in wanted_metadata}
        try:
            vals = []
            for player in entry['roster']['scorecards']:
                d = {k: player[k] for k in wanted_scorecard}
                if playerd:
                    d = dict(**d, **playerd.get(d['draftableId'], {}))
                vals.append(dict(**draft_metadata, **d))
            return vals

        except KeyError:
            logging.exception(entry)
            return []

    def filter_contests_by_size(self, data, size=None):
        """Filters mycontests for specific type, say 3-Player"""
        return [c for c in data if f'{size}-Player' in c['ContestName']]

    def get_entry_key(self, leaderboard, username):
        """Gets entry key from leaderboard"""
        try:
            return [l['MegaEntryKey'] for l in leaderboard['Leaderboard'] if l['UserName'] == username][0]
        except (IndexError, KeyError):
            return [l['EntryKey'] for l in leaderboard['Leaderboard'] if l['UserName'] == username][0]
        raise ValueError(f"No entry key available for contest {leaderboard['Leader']['MegaContestKey']}") 

    def is_bestball_contest(self, content):
        """Tests if it is a bestball contest
        
        Args:
            content (dict): contest dict

        Returns:
            bool
        """
        return content.get('GameTypeId') == self.bestball_gametype_id

    def mycontests(self, htmlfn=None, jsonfn=None):
        """Parses mycontests.html page / contests javascript variable
        
        Args:
            htmlfn (Path or str): path of html file
            jsonfn (Path or str): path of json file

        Returns:
            list: of contest dict
        """
        if htmlfn:
            # read text of file into content variable
            try:
                content = htmlfn.read_text()
            except:
                content = Path(htmlfn).read_text()

            # now extract the contests variable and return parsed JSON
            # RIGHT NOW IS LIVE ONLY
            patt = re.compile(r'var contests = \{.*?live\: (\[.*?\]),', re.MULTILINE | re.DOTALL)
            match = re.search(patt, content)
            if match:
                return json.loads(match.group(1))
            return None
        elif jsonfn:
            # TO IMPLEMENT
            pass
        else:
            raise ValueError('htmlfn or jsonfn cannot both be None')

    def ownership(self, rosterdf, username, contest_size=None):
        """Calculates ownership across rosters

        Args:
            rosterdf (DataFrame): of rosters
            username (str): the username to get ownership for

        Returns:
            DataFrame with columns
            displayName, n_contests, n_own, vs_field
        """
        # first determine overall ownership
        # will be some players I don't own that 
        # are excluded if start with my ownership
        n_contests = len(rosterdf['contestKey'].unique())
        overall_ownership = (
            rosterdf
            .groupby('displayName')
            .agg(tot_drafted=('contestKey', 'count')) 
            .assign(tot_drafted_pct=lambda df_: df_.tot_drafted/n_contests*100)
        )

        summ = (
            rosterdf
            .query(f"userName == '{username}'")
            .groupby('displayName')
            .agg(user_drafted=('contestKey', 'count'))
            .assign(user_drafted_pct=lambda df_: df_.user_drafted/n_contests*100)
        )

        df = overall_ownership.loc[:, ['tot_drafted_pct']].join(summ, how='left').fillna(0)
        df['user_drafted'] = df['user_drafted'].astype(int)

        if contest_size:
            df['vs_field'] = df['user_drafted_pct'] - (df['tot_drafted_pct'] / contest_size)

        df.insert(0, 'n_contests', n_contests)
        return df    

    def player_pool(self, id=None, draftables=None):
        """Takes parsed draftables (from file or request) and creates player pool
           Can also pass id and will read draftables file from data directory

        Args:
            id (int): draftables Id
            draftables (dict): parsed JSON resource 

        Returns:
            list: of dict with keys
            'draftableId', 'displayName', 'playerId', 'playerDkId', 'position', 'teamAbbreviation'
        """
        if id:
            fn = self._draftablesfn(id)
            draftables = self._to_obj(fn)
        if not isinstance(draftables, dict):
            raise ValueError('Did not properly load draftables')
        wanted = self.PLAYERPOOL_FIELDS
        return [{k: item[k] for k in wanted} for item in draftables['draftables']]
    
    def player_pool_dict(self, id=None, draftables=None):
        """Takes parsed draftables (from file or request) and creates player pool dict with key of draftableId
           Can also pass id and will read draftables file from data directory

        Args:
            id (int): draftables Id
            draftables (dict): parsed JSON resource 

        Returns:
            dict of dict: key is draftableId, 
            value is dict with keys 'displayName', 'playerId', 'playerDkId', 'position', 'teamAbbreviation'
        """
        wanted = self.PLAYERPOOL_FIELDS.copy()
        key = wanted.pop(0)
        return {item[key]: {k:item[k] for k in wanted}
                for item in self.player_pool(draftables=draftables, id=id)}
    
    def standings(self, leaderboards, username):
        """Calculates overall standings for user by contest type
        
        Args:
            leaderboards (list): of dict
            username (str): the user to track standings for

        Returns:
            DataFrame
        """
        return pd.DataFrame(leaderboards).query(f"userName == '{username}'")



if __name__ == '__main__':
    pass
