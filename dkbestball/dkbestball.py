# -*- coding: utf-8 -*-
"""
dkbestball.py

Examples:

    import os
    from pathlib import Path
    from dkbestball import Analyzer

    user = os.getenv('DK_BESTBALL_USER')
    basedir = Path.home() / 'workspace' / 'dkbestball-data'
    a = Analyzer(user, basedir)

    # show standings: tournament, 3man, 6man, 12man leagues
    std = a.standings()
    a.standings_summary(std, 't')
    a.standings_summary(std, '3m')
    a.standings_summary(std, '6m')
    a.standings_summary(std, '12m')

    # get ownership

TODO: add financial measures

"""
from collections import ChainMap, defaultdict
from functools import lru_cache
import itertools
import json
import logging
from pathlib import Path
import pickle
import re
import time
import zipfile

import browser_cookie3
import pandas as pd
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


class Parser:
    """Parses DK bestball contest files"""

    PLAYERPOOL_FIELDS = [
        'draftableId', 'playerId', 'playerDkId', 'displayName', 'position',
        'teamAbbreviation'
    ]

    def __init__(self, bestball_gametype_id=145):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.bestball_gametype_id = bestball_gametype_id

    @staticmethod
    def _pctcol(val):
        return f'{round(val * 100, 2)}%'

    @staticmethod
    def _to_dataframe(container):
        """Converts container to dataframe"""
        return pd.DataFrame(container)

    @staticmethod
    def _to_obj(pth):
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
            'ContestId', 'ContestName', 'BuyInAmount', 'MaxNumberPlayers',
            'DraftGroupId', 'GameTypeId', 'TopPayout', 'UserContestId',
            'ResultsRank', 'TotalPointsOpp', 'UsernameOpp', 'PlayerPoints'
        ]

        d = {k: contest.get(k) for k in wanted}
        d['ClockType'] = 'slow' if 'Slow Draft' in contest[
            'ContestName'] else 'fast'
        return d

    def contest_leaderboard(self, content):
        """Parses contest leaderboard

        Args:
            content (dict): leaderboard dict

        Returns:
            list: of dict
        """
        vals = []
        wanted = ['UserName', 'UserKey', 'Rank', 'FantasyPoints']
        lbkey = 'Leaderboard'
        ckey = 'MegaContestKey'
        ekey = 'MegaEntryKey'
        for item in content[lbkey]:
            d = {k: item.get(k) for k in wanted}
            d[ckey] = item[ckey]
            d[ekey] = item[ekey]
            vals.append(d)
        return vals

    def contest_roster(self, content, playerd=None):
        """Parses roster from single contest.
           DK doesn't seem to have saved draft order.

        Args:
            content (dict): parsed draft resource
            playerd (dict): additional player data

        Returns:
            list: of dict

        """
        entry = content['entries'][0]
        wanted_metadata = [
            'draftGroupId', 'contestKey', 'entryKey', 'lineupId', 'userName',
            'userKey'
        ]
        wanted_scorecard = ['displayName', 'draftableId']
        draft_metadata = {k: entry.get(k) for k in wanted_metadata}
        vals = []
        for player in entry['roster']['scorecards']:
            d = {k: player[k] for k in wanted_scorecard}
            if playerd:
                d = dict(ChainMap(d, playerd.get(d['draftableId'], {})))
            vals.append(dict(**draft_metadata, **d))
        return vals

    def get_entry_key(self, leaderboard, username):
        """Gets entry key from leaderboard"""
        return [
            lbd['MegaEntryKey']
            for lbd in leaderboard['Leaderboard']
            if lbd['UserName'] == username
        ][0]

    def is_bestball_contest(self, content):
        """Tests if it is a bestball contest

        Args:
            content (dict): contest dict

        Returns:
            bool
        """
        return content.get('GameTypeId') == self.bestball_gametype_id

    def mycontests(self, htmlfn):
        """Parses mycontests.html page / contests javascript variable

        Args:
            htmlfn (Path or str): path of html file

        Returns:
            list: of contest dict
        """
        # read text of file into content variable
        try:
            content = htmlfn.read_text()
        except AttributeError:
            content = Path(htmlfn).read_text()

        # now extract the contests variable and return parsed JSON
        # RIGHT NOW IS LIVE ONLY
        patt = re.compile(r'var contests = \{.*?live\: (\[.*?\]),',
                          re.MULTILINE | re.DOTALL)
        match = re.search(patt, content)
        if match:
            return json.loads(match.group(1))
        return None

    def player_pool(self, draftables_fn=None, draftables=None):
        """Takes parsed draftables (from file or request) and creates player pool
           Can also pass path and will read draftables file

        Args:
            draftables_fn (Path): draftables path
            draftables (dict): parsed JSON resource

        Returns:
            list: of dict with keys
            'draftableId', 'displayName', 'playerId', 'playerDkId',
            'position', 'teamAbbreviation'
        """
        if draftables_fn:
            draftables = self._to_obj(draftables_fn)
        if not isinstance(draftables, dict):
            raise ValueError('Did not properly load draftables')
        return [{k: item[k]
                 for k in self.PLAYERPOOL_FIELDS}
                for item in draftables['draftables']]

    def player_pool_dict(self, draftables_fn=None, draftables=None):
        """Takes parsed draftables (from file or request) and
           creates player pool dict with key of draftableId
           Can also pass id and will read draftables file from data directory

        Args:
            draftables_fn (Path): draftables path
            draftables (dict): parsed JSON resource

        Returns:
            dict of dict: key is draftableId,
            value is dict with keys 'displayName', 'playerId', 'playerDkId',
                                    'position', 'teamAbbreviation'
        """
        wanted = self.PLAYERPOOL_FIELDS.copy()
        key = wanted.pop(0)
        pool = self.player_pool(draftables_fn=draftables_fn,
                                draftables=draftables)
        return {item[key]: {k: item[k] for k in wanted} for item in pool}


class Analyzer:
    """Encapsulates analysis / summary of rosters and results"""

    def __init__(self, username, datadir):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.username = username
        self.datadir = datadir

    @property
    def mycontests_path(self):
        return self.datadir / 'mycontests.pkl'

    @property
    def myentrykeys_path(self):
        return self.datadir / 'myentrykeys.pkl'

    @property
    def myleaderboards_path(self):
        return self.datadir / 'myleaderboards.pkl'

    @property
    def myrosters_path(self):
        return self.datadir / 'myrosters.pkl'

    def contest_type(self, s):
        """Gets contest type from contest name"""
        if 'Millionaire' in s:
            return 'Tournament'
        if 'Play-Action' in s:
            return 'Tournament'
        if '12-Player' in s:
            return '12-Man'
        if '6-Player' in s:
            return '6-Man'
        if '3-Player' in s:
            return '3-Man'
        return 'Unknown'

    @lru_cache(maxsize=128)
    def mycontests(self):
        with self.mycontests_path.open('rb') as f:
            return pickle.load(f)

    @lru_cache(maxsize=128)
    def myleaderboards(self):
        with self.myleaderboards_path.open('rb') as f:
            return pickle.load(f)

    @lru_cache(maxsize=128)
    def myrosters(self):
        with self.myrosters_path.open('rb') as f:
            return pickle.load(f)

    def financial_summary(self, contest_col='ContestName'):
        """Summarizes financial results"""
        std = self.standings()
        std['ContestType'] = std[contest_col].apply(self.contest_type)
        gb = std.groupby(['ContestType', 'BuyInAmount'], as_index=False)
        aggs = (('UserKey', 'count'), ('BuyInAmount', 'sum'), ('TokensWon',
                                                               'sum'))
        summ = gb.agg(Entries=aggs[0], Paid=aggs[1], Won=aggs[2])
        summ['ROI'] = ((summ.Won - summ.Paid) / summ.Paid).mul(100).round(1)
        return summ

    def ownership(self):
        df = pd.DataFrame(self.myrosters())
        grpcols = ['displayName', 'position', 'teamAbbreviation']
        gb = df.groupby(grpcols, as_index=False)
        summ = gb.agg(n=('userName', 'count'))
        summ['tot'] = len(df['entryKey'].unique())
        summ['pct'] = (summ['n'] / summ['tot']).mul(100).round(1)
        return summ.sort_values('pct', ascending=False)

    def positional_ownership(self, df, pos, thresh=10):
        """Gets positional ownership"""
        q = f'position == "{pos}" and pct > {thresh}'
        return self.ownership().query(q)

    def standings(self):
        """Gets standings dataframe"""
        df = pd.DataFrame(itertools.chain.from_iterable(self.myleaderboards()))
        df = df.loc[df.UserName == self.username, :]
        df['MegaContestKey'] = df['MegaContestKey'].astype(int)
        cdf = pd.DataFrame(self.mycontests())
        wanted = [
            'MegaContestId', 'ContestName', 'BuyInAmount', 'NumberOfEntrants',
            'TokensWon'
        ]
        cdf = cdf.loc[:, wanted].set_index('MegaContestId')
        return df.join(cdf, how='left', on='MegaContestKey')

    def standings_summary(self, df, contest_type):
        """Gets standing summary for contest type"""
        s = {
            '3m': '3-Player',
            '6m': '6-Player',
            '12m': '12-Player',
            'pa': 'Action',
            'm': 'Millionaire',
            't': r'\['
        }
        std = self.standings()
        std = std.loc[std.ContestName.str.contains(s.get(contest_type), ' '), :]
        return (std['Rank'].value_counts().reset_index().sort_values(
            'index').set_axis(['place', 'n_teams'], axis=1).assign(
                pct=lambda df_: round(df_.n_teams / len(std), 2)))

    def tournament_roster(self, df, contest_key, wanted=None):
        """Single tournament roster"""
        default_wanted = ['displayName', 'position', 'teamAbbreviation']
        wanted = wanted if wanted else default_wanted
        crit1 = df.contestKey == str(contest_key)
        crit2 = df.userName == self.username
        return df.loc[crit1 & crit2, wanted]

    def tournament_rosters(self):
        """Gets roster for play-action & millionaire tournaments"""
        myc = self.mycontests()
        df = pd.DataFrame(myc)
        r = self.myrosters()
        rdf = pd.DataFrame(r)
        rdf['contestKey'] = rdf['contestKey'].astype(int)

        # play action
        pa = df.loc[df.ContestName.str.contains('Play-Action'), :]
        crit1 = rdf.contestKey.isin(pa.MegaContestId.values)
        crit2 = rdf.userName == 'sansbacon'
        mypa = rdf.loc[crit1 & crit2, :]
        gb = mypa.groupby(['displayName', 'position'], as_index=False)
        padf = gb.agg(n_plyr=('draftableId', 'count'))
        padf['n'] = len(pa)
        padf['pct'] = (padf['n_plyr'] / padf['n']).mul(100).round(2)
        padf['contest'] = 'Play Action'

        # millionaire
        mill = df.loc[df.ContestName.str.contains('Millionaire'), :]
        crit1 = rdf.contestKey.isin(mill.MegaContestId.values)
        crit2 = rdf.userName == 'sansbacon'
        mym = rdf.loc[crit1 & crit2, :]
        gb = mym.groupby(['displayName', 'position'], as_index=False)
        milldf = gb.agg(n_plyr=('draftableId', 'count'))
        milldf['n'] = len(pa)
        milldf['pct'] = (milldf['n_plyr'] / milldf['n']).mul(100).round(2)
        milldf['contest'] = 'Millionaire'

        # combined dataframes
        return pd.concat([padf, milldf], ignore_index=True)

    def tournament_ownership(self, df, tournament=None, pos=None):
        """Shows tournament ownership by tournament and position"""
        if tournament:
            df = df.loc[df.contest == tournament, :]
        if pos:
            df = df.loc[df.position == pos, :]
        return df.sort_values('pct', ascending=False)


class Updater:
    """Encapsulates scraping/parsing activity for weekly updates"""

    def __init__(self, username, datadir, sleep_time=.1):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.username = username
        self.datadir = datadir
        self._s = Scraper()
        self._p = Parser()
        self.sleep_time = sleep_time

    @property
    def mycontests_path(self):
        return self.datadir / 'mycontests.pkl'

    @property
    def myentrykeys_path(self):
        return self.datadir / 'myentrykeys.pkl'

    @property
    def myleaderboarddir_path(self):
        return self.datadir / 'leaderboards'

    @property
    def myleaderboards_path(self):
        return self.datadir / 'myleaderboards.pkl'

    @property
    def myrosters_path(self):
        return self.datadir / 'myrosters.pkl'

    @property
    def myrosterdir_path(self):
        return self.datadir / 'rosters'

    def mycontests(self):
        """Gets contests"""
        mycontestsfile = self.datadir / 'mycontests.html'
        return self._p.mycontests(mycontestsfile)

    def update_analysis_files(self):
        """Updates analysis files"""
        print('updated analysis files')

    def update_parsed_files(self):
        """Updates pickled files of leaderboards and rosters"""

        # mycontests
        with self.mycontests_path.open('wb') as f:
            mycontests = self.mycontests()
            pickle.dump(mycontests, f)

        # leaderboards and entrykeys
        mylbs = []
        entry_keys = defaultdict(list)
        for pth in self.myleaderboarddir_path.glob('*.json'):
            data = self._p._to_obj(pth)
            leaderboard = self._p.contest_leaderboard(data)
            mylbs.append(leaderboard)
            for item in leaderboard:
                contest_key = int(item['MegaContestKey'])
                entry_key = int(item['MegaEntryKey'])
                entry_keys[contest_key].append(entry_key)

        # save to disk
        with self.myentrykeys_path.open('wb') as f:
            pickle.dump(entry_keys, f)
        with self.myleaderboards_path.open('wb') as f:
            pickle.dump(mylbs, f)

        # myrosters
        myrosters = []
        for pth in self.myrosterdir_path.glob('*.json'):
            data = self._p._to_obj(pth)
            draftable_id = data['entries'][0]['draftGroupId']
            draftable_path = self.datadir / f'draftables_{draftable_id}.json'
            draftables = self._p._to_obj(draftable_path)
            playerd = self._p.player_pool_dict(draftables=draftables)
            try:
                myrosters += self._p.contest_roster(data, playerd)
            except KeyError:
                contest_key = data['entries'][0]['contestKey']
                entry_key = data['entries'][0]['entryKey']
                print(f"No roster for contest {contest_key}, entry {entry_key}")
        with self.myrosters_path.open('wb') as f:
            pickle.dump(myrosters, f)

    def update_raw_files(self, update_rosters=False):
        """Updates leaderboards and rosters"""
        # create new zip and overwrite old file if succeeds
        zipfn = self.myleaderboarddir_path / 'leaderboards_new.zip'
        old_zipfn = self.myleaderboarddir_path / 'leaderboards.zip'
        with zipfile.ZipFile(zipfn, 'w') as myzip:
            for pth in self.myleaderboarddir_path.glob('*.json'):
                myzip.write(pth, pth.name)
        zipfn.rename(old_zipfn)

        # loop through contests
        for item in self.mycontests():

            # get contest and draftgroup ids
            contest_id = item['ContestId']
            draftgroup_id = item['DraftGroupId']
            msg = f'starting contest {contest_id}, dg {draftgroup_id}'
            logging.info(msg)

            # save leaderboard to disk
            pth = self.datadir / 'leaderboards' / f'{contest_id}.json'
            lb = self._s.contest_leaderboard(contest_id=contest_id)
            with pth.open('w') as fh:
                json.dump(lb, fh)
            time.sleep(self.sleep_time)

            if update_rosters:
                # now get rosters
                # get entry_keys from leaderboard
                for lb in self._p.contest_leaderboard(lb):
                    entry_key = int(lb['MegaEntryKey'])
                    pth = self.datadir / 'rosters' / f'{entry_key}.json'
                    if not pth.is_file():
                        roster = self._s.contest_roster(draftgroup_id,
                                                        entry_key)
                        with pth.open('w') as fh:
                            json.dump(roster, fh)
                        time.sleep(self.sleep_time)


if __name__ == '__main__':
    pass
