"""
get_files.py

save dk leaderboards and scoring to local directories
"""

import json
import logging
from pathlib import Path
import time

import click
import pandas as pd
import requests

try:
    from dkbestball import Parser, Scraper
except ModuleNotFoundError:
    import sys
    pth = Path(__file__).parent.parent
    sys.path.append(str(pth))
    from dkbestball import Parser, Scraper


@click.command()
@click.option('-u', '--username', type=str, help='DK Username')
@click.option('-f', '--fn', type=str, help='Path to mycontestsfile')
@click.option('-d', '--datadir', type=str, help='Path to data directory')
def run(username, fn, datadir):
    """Main script"""    
    # SETUP
    s = Scraper()
    p = Parser()
    mycontestsfile = Path(fn)
    if not mycontestsfile.is_file():
        raise ValueError(f'Invalid mycontestsfile {fn}')
    data_dir = Path(datadir)
    if not data_dir.is_dir():
        raise ValueError(f'Invalid data directory {datadir}')
    
    # STEP ONE - get mycontests
    mycontests = p.mycontests(mycontestsfile)

    # STEP TWO - get leaderboards and rosters
    # TODO: archive old files before overwriting
    # leaderboard_archive.zip, roster_archive.zip
    for item in mycontests:
        
        # get contest and draftgroup ids
        contest_id = item['ContestId']
        draftgroup_id = item['DraftGroupId']

        # save leaderboard to disk
        # TODO: adjust for archiving feature
        pth = data_dir / 'leaderboards' / f'{contest_id}.json'
        if not pth.is_file():
            logging.info(f'Getting {contest_id}')
            lb = s.contest_leaderboard(contest_id=contest_id)
            with pth.open('w') as fh:
                json.dump(lb, fh)
            time.sleep(1)
        else:
            lb = p._to_obj(pth)

        # now get roster 
        # get entry_key from leaderboard
        # sometimes is entry key, sometimes mega entry key
        # is embedded in the user's results
        entry_key = p.get_entry_key(lb, username)

        # save roster to disk if 
        # TODO: adjust for archiving feature
        pth = data_dir / 'rosters' / f'{entry_key}.json'
        if not pth.is_file():
            logging.info(f'Getting {entry_key}')
            roster = s.contest_roster(draftgroup_id, entry_key)
            with pth.open('w') as fh:
                json.dump(roster, fh)
            time.sleep(1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()