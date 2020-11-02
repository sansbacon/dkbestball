# parse_files.py
# gets leaderboards and scoring from local directories
# run this after updating those files with get_files.py
# TODO: turn into cli

import logging
from pathlib import Path
import pandas as pd

from dkbestball import Parser


logging.basicConfig(level=logging.INFO)


def contests(fn, filter_size=None):
    p = Parser()
    mycontests = p.mycontests(fn)
    if filter_size:
        return p.filter_contests_by_size(mycontests, size=filter_size)
    return mycontests


def contest_ids(contests):
    return [item['ContestId'] for item in contests]


def rosters():
    p = Parser()
    rosters = []
    for pth in p.ROSTER_DIR.glob('*.json'):
        data = p._to_obj(pth)
        playerd = p.player_pool_dict(id=data['entries'][0]['draftGroupId'])
        rosters += p.contest_roster(data, playerd)
    return rosters
    #rosterdf = pd.DataFrame(rosters)   
    #df.displayName.value_counts(normalize=True).mul(900).sort_values(ascending=False)

    #############################################################


def ownership():
    p = Parser()
    mycontestsfile = Path.home() / 'workspace' / 'dkbestball' / 'tests' / 'mycontests.html'
    mycontests = p.mycontests(mycontestsfile)
    tman_ids = [item['ContestId'] for item in p.filter_contests_by_size(mycontests, size=3)]

    # have to get entry keys from contests
    # then can find associated rosters
    entry_keys = []    
    for pth in [item for item in p.LEADERBOARD_DIR.glob('*.json')]:
        if int(pth.stem) in tman_ids:
            data = p._to_obj(pth)
            lbdf = pd.DataFrame(p.contest_leaderboard(data))
            entry_keys.append(lbdf.loc[lbdf['UserName'] == 'sansbacon', 'MegaEntryKey'].values[0])

    # find associated rosters
    rosters = []
    for pth in p.ROSTER_DIR.glob('*.json'):
        if pth.stem in entry_keys:
            data = p._to_obj(pth)
            playerd = p.player_pool_dict(id=data['entries'][0]['draftGroupId'])
            rosters += p.contest_roster(data, playerd)

    # print summary
    (
      pd.DataFrame(rosters)
      .groupby(['displayName', 'position', 'teamAbbreviation'])
      .agg(n=('userName', 'count'))
      .assign(tot=len(tman_ids))
      .assign(pct=lambda df_: (df_.n / df_.tot).mul(100).round(1))
      .reset_index()
      .sort_values('pct', ascending=False)
      .head(50)
    )


if __name__ == '__main__':
    pass
