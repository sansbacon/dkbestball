import json
import logging
import pickle
import time
import zipfile

from dkbestball import Parser, Scraper


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
    def mydata_path(self):
        return self.datadir / 'mydata.pkl'

    @property
    def myleaderboarddir_path(self):
        return self.datadir / 'leaderboards'

    @property
    def myrosterdir_path(self):
        return self.datadir / 'rosters'

    def mycontests(self):
        """Gets contests"""
        if self.mycontests_path.is_file():
            with self.mycontests_path.open('rb') as f:
                return pickle.load(f)
        mycontestsfile = self.datadir / 'mycontests.html'
        return self._p.mycontests(mycontestsfile)

    def update_parsed_files(self):
        """Updates pickled files of leaderboards and rosters"""
        data = []
        for c in self.mycontests():
            d = {'entry_keys': []}
            d['contest_key'] = str(c['MegaContestId'])
            d['contest_name'] = c['ContestName']
            d['contest_size'] = c['MaxNumberPlayers']
            d['entry_fee'] = c['BuyInAmount']
            d['draftgroup_id'] = c['DraftGroupId']
            d['winnings'] = c['TokensWon']
            d['leader_points'] = c['TotalPointsOpp']
            d['my_place'] = c['ResultsRank']
            d['my_points'] = c['PlayerPoints']

            lbfile = self.myleaderboarddir_path / f"{d['contest_key']}.json"
            if not lbfile.is_file():
                logging.error(f'Could not find {lbfile}')

            # get my entry key
            for item in self._p.contest_leaderboard(self._p._to_obj(lbfile)):
                entry_key = str(item['MegaEntryKey'])
                d['entry_keys'].append(entry_key)
                if item['UserName'] == self.username:
                    d['my_entry_key'] = entry_key

            # get my roster
            roster_path = self.myrosterdir_path / f"{d['my_entry_key']}.json"
            roster_obj = self._p._to_obj(roster_path)
            draftable_path = self.datadir / f"draftables_{d['draftgroup_id']}.json"
            draftables = self._p._to_obj(draftable_path)
            playerd = self._p.player_pool_dict(draftables=draftables)

            try:
                d['myroster'] = self._p.contest_roster(roster_obj, playerd)
            except KeyError:
                print(
                    f"No roster for contest {d['contest_key']}, entry {d['my)entry_key']}"
                )

            data.append(d)

        with self.mydata_path.open('wb') as f:
            pickle.dump(data, f)

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
