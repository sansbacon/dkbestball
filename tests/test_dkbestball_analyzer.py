# -*- coding: utf-8 -*-
# test_dkbestball.py
# SET DK_BESTBALL_USERNAME env variable if not exist

import os

import pandas as pd
import pytest

from dkbestball import Analyzer


@pytest.fixture
def a(test_directory):
    return Analyzer(username=os.getenv('DK_BESTBALL_USERNAME'),
                    datadir=test_directory)


def test_init(test_directory):
    obj = Analyzer(username=os.getenv('DK_BESTBALL_USERNAME'),
                   datadir=test_directory)
    assert obj
    assert obj.username is not None
    assert obj.datadir.is_dir()


def test_mycontests_path(a):
    assert a.mycontests_path.is_file()


def test_myentrykeys_path(a):
    return a.datadir / 'myentrykeys.pkl'


def test_myleaderboards_path(a):
    return a.datadir / 'myleaderboards.pkl'


def test_myrosters_path(a):
    return a.datadir / 'myrosters.pkl'


def test_mycontests(a):
    assert a.mycontests()


def test_myleaderboards(a):
    assert a.myleaderboards()


def test_myrosters(a):
    assert a.myrosters
