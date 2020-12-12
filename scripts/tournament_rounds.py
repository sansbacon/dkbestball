import logging
import os
from pathlib import Path

import pandas as pd
from dkbestball import Parser, Scraper


logger = logging.getLogger()
logger.setLevel(logging.INFO)

s = Scraper()
p = Parser()

# draftgroupid 
draft_group_id = 42308
basedir = Path(os.getenv('DKBESTBALL_DATA_DIR'))
fn = basedir / 'draftables' / f'{draft_group_id}.json'
ppd = p.player_pool_dict(draftables_fn=fn)

# get mycontests
logging.info('Getting my contests')
myc = p.mycontests(html=s.mycontests())

# get rosters
rosters = []

for item in [c for c in myc['live'] if 'Tournament Round' in c['ContestName']]:
    contest_id = item['ContestId']
    draftgroup_id = item['DraftGroupId']
    msg = f'starting contest {contest_id}, dg {draftgroup_id}'
    logging.info(msg)
    lb = s.contest_leaderboard(contest_id=contest_id)

    # get entry keys from leaderboard
    for lb in p.contest_leaderboard(lb):
        entry_key = int(lb['entryKey'])
        roster = s.contest_roster(draftgroup_id, entry_key)
        rosters += p.contest_roster(roster, ppd)

rdf = pd.DataFrame(rosters)

(
rdf
.loc[rdf.userName == 'sansbacon', :]
.groupby(['displayName', 'teamAbbreviation', 'position'], as_index=False)
.agg(n=('entryKey','count'))
)
