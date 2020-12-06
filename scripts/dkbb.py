import logging
import os
from pathlib import Path

import click
from tabulate import tabulate

from dkbestball import Analyzer, Updater

COMPONENT_TYPE = str
COMPONENT_HELP = 'Update all data or specific components'


def _dump(df, fmt='presto', idx='never'):
    """Dumps df to terminal"""
    print('\n', tabulate(df, headers='keys', tablefmt=fmt, showindex=idx))


@click.group()
@click.pass_context
@click.option('--quiet', is_flag=True, default=False, help="Silence logger.")
def main(ctx, quiet):
    username = os.getenv('DK_BESTBALL_USERNAME')
    datadir = Path(os.getenv('DKBESTBALL_DATA_DIR'))
    ctx.obj = {
        'u': Updater(username, datadir),
        'a': Analyzer(username, datadir)
    }
    level = logging.ERROR if quiet else logging.INFO
    logging.basicConfig(level=level)


# Update Group
@main.group()
@click.pass_context
def update(ctx):
    pass


@update.command()
@click.pass_context
@click.option('--update_rosters', '-r', is_flag=True, help="Update rosters.")
def raw(ctx, update_rosters):
    logging.info('Updating raw files')
    ctx.obj['u'].update_raw_files(update_rosters=update_rosters)


@update.command()
@click.pass_context
@click.option('--update_contests', '-c', is_flag=True, help="Update contests.")
@click.option('--update_rosters', '-r', is_flag=True, help="Update rosters.")
def parsed(ctx, update_contests, update_rosters):
    logging.info('Updating parsed files')
    ctx.obj['u'].update_parsed_files(update_contests=update_contests,
                                     update_rosters=update_rosters)


# Analyze Group
@main.group()
@click.pass_context
def analyze(ctx):
    pass


@analyze.command()
@click.pass_context
def financial(ctx):
    a = ctx.obj['a']
    df = a.financial_summary()
    _dump(df)


@analyze.command()
@click.pass_context
@click.option('-p', '--pos', type=str, default=None, help='Position')
def ownership(ctx, pos):
    a = ctx.obj['a']
    df = a.ownership()
    if not pos:
        _dump(df)
    else:
        _dump(a.positional_ownership(df, pos.upper()))


@analyze.command()
@click.pass_context
@click.option('-t', '--contest_type', type=str, help='Contest type')
def standings(ctx, contest_type):
    a = ctx.obj['a']
    _dump(a.standings_summary(contest_type))


if __name__ == '__main__':
    main()
