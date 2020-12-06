from functools import lru_cache
import logging
import pickle

import pandas as pd


class Analyzer:
    """Encapsulates analysis / summary of rosters and results"""

    CONTEST_CODES = {
        '3m': '3-Player',
        '6m': '6-Player',
        '12m': '12-Player',
        'pa': 'Action',
        'm': 'Millionaire',
        't': 'Tournament'
    }

    DATA_COLUMNS = [
        'entry_keys', 'contest_key', 'contest_name', 'contest_size',
        'entry_fee', 'draftgroup_id', 'winnings', 'leader_points', 'my_place',
        'my_points', 'my_entry_key', 'myroster', 'contest_type'
    ]

    FINANCIAL_COLUMNS = [
        'contest_type', 'entry_fee', 'Entries', 'Paid', 'Won', 'ROI'
    ]

    OWNERSHIP_COLUMNS = [
        'displayName', 'position', 'teamAbbreviation', 'n', 'tot', 'pct'
    ]

    ROSTER_COLUMNS = [
        'draftGroupId', 'contestKey', 'entryKey', 'lineupId', 'userName',
        'userKey', 'playerId', 'playerDkId', 'displayName', 'position',
        'teamAbbreviation', 'draftableId'
    ]

    STANDINGS_COLUMNS = [
        'contest_key', 'contest_name', 'contest_type', 'entry_fee',
        'contest_size', 'my_place', 'winnings', 'my_points', 'leader_points'
    ]

    def __init__(self, username, datadir):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.username = username
        self.datadir = datadir
        self.mydata_path = self.datadir / 'mydata.pkl'
        self.data = pd.DataFrame(self._load_data())
        self.data['contest_type'] = self.data['contest_name'].apply(
            self.contest_type)

    def _filter_rosters(self, df, contests):
        """Filters roster by contest(s)"""
        return df.loc[df.contestKey.isin(contests), :]

    def _load_data(self):
        """Loads data file"""
        with self.mydata_path.open('rb') as f:
            return pickle.load(f)

    @lru_cache(maxsize=128)
    def _tournament_keys(self, contest_type, keycol):
        """Gets key column for given contest type"""
        return self.data.loc[self.data['contest_type'] == contest_type, keycol]

    def contest_type(self, s):
        """Gets contest type from contest name"""
        val = 'Unknown'
        if 'Tournament' in s:
            val = 'Tournament'
        if 'Millionaire' in s:
            val = 'Tournament'
        if 'Play-Action' in s:
            val = 'Tournament'
        if '12-Player' in s:
            val = '12-Man'
        if '6-Player' in s:
            val = '6-Man'
        if '3-Player' in s:
            val = '3-Man'
        return val

    def financial_summary(self):
        """Summarizes financial results"""
        std = self.standings()
        gb = std.groupby(['contest_type', 'entry_fee'], as_index=False)
        aggs = (('contest_key', 'count'), ('entry_fee', 'sum'), ('winnings',
                                                                 'sum'))
        summ = gb.agg(Entries=aggs[0], Paid=aggs[1], Won=aggs[2])
        summ['ROI'] = ((summ.Won - summ.Paid) / summ.Paid).mul(100).round(1)
        return summ

    @lru_cache(maxsize=128)
    def myrosters(self):
        """
            draftGroupId             37605
            contestKey            89460375
            entryKey            2062649745
            lineupId                    -1
            userName             sansbacon
            userKey                 725157
            playerId                380750
            playerDkId               20426
            displayName         Cam Newton
            position                    QB
            teamAbbreviation            NE
            draftableId           14885230

        """
        return pd.concat(
            [pd.DataFrame(row.myroster) for row in self.data.itertuples()])

    def ownership(self, df=None):
        """Gets player ownership

        Args:
            df (DataFrame): matches myrosters

        Returns:
            DataFrame with columns
            displayName, position, teamAbbreviation,
            n, tot, pct
        """
        if df is None:
            df = self.myrosters()
        grpcols = ['displayName', 'position', 'teamAbbreviation']
        gb = df.groupby(grpcols, as_index=False)
        summ = gb.agg(n=('userName', 'count'))
        summ['tot'] = len(df['entryKey'].unique())
        summ['pct'] = (summ['n'] / summ['tot']).mul(100).round(1)
        return summ.sort_values('pct', ascending=False)

    def positional_ownership(self, df=None, pos='QB', thresh=10):
        """Gets positional ownership"""
        if df is None:
            df = self.ownership()
        q = f'position == "{pos}" and pct > {thresh}'
        return df.query(q)

    def standings(self):
        """Gets standings dataframe"""
        return self.data.loc[:, self.STANDINGS_COLUMNS]

    def standings_summary(self, contest_type):
        """Gets standing summary for contest type

        """
        std = self.standings()
        std = std.loc[std.contest_name.str.
                      contains(self.CONTEST_CODES.get(contest_type), ' '), :]
        return (std['my_place'].value_counts().reset_index().sort_values(
            'index').set_axis(['place', 'n_teams'], axis=1).assign(
                pct=lambda df_: round(df_.n_teams / len(std), 2)))

    def tournament_contests(self):
        """Gets tournament contests"""
        return self._tournament_keys(contest_type='Tournament',
                                     keycol='contest_key')

    def tournament_entries(self):
        return self._tournament_keys(contest_type='Tournament',
                                     keycol='my_entry_key')

    def tournament_ownership(self):
        """Shows tournament ownership"""
        return self.ownership(self.tournament_rosters())

    def tournament_rosters(self):
        df = self.myrosters()
        return self._filter_rosters(df, self.tournament_contests())


if __name__ == '__main__':
    pass
