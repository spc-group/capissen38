from queue import Queue
from unittest.mock import MagicMock

import numpy as np
import pytest
from bluesky_adaptive.recommendations import NoRecommendation

from haven.plans import _auto_gain, auto_gain


def test_plan_recommendations(ion_chamber):
    # Make a fake queue that accepts the second step
    queue = Queue()
    queue.put({ion_chamber.preamp.gain_level.name: 12})
    queue.put(None)
    # Prepare the plan and make sure it generates messages
    plan = auto_gain(ion_chambers=[ion_chamber], queue=queue)
    msgs = list(plan)
    # Make sure the plan sets the gain values properly
    set_msgs = [msg for msg in msgs if msg.command == "set"]
    assert len(set_msgs) == 2
    assert set_msgs[0].args[0] == 13  # Starting point
    assert set_msgs[1].args[0] == 12  # First adaptive point
    # Make sure the plan triggers the ion chamber
    trigger_msgs = [msg for msg in msgs if msg.command == "trigger"]
    assert len(trigger_msgs) == 2


@pytest.mark.parametrize(
    "prefer,target_volts",
    [("middle", 2.5), ("lower", 0.5), ("upper", 4.5)],
)
async def test_plan_prefer_arg(ion_chamber, monkeypatch, prefer, target_volts):
    """Check that the *prefer* argument works properly."""
    queue = Queue()
    queue.put({ion_chamber.preamp.gain_level.name: 12})
    queue.put(None)
    monkeypatch.setattr(_auto_gain, "GainRecommender", MagicMock())
    plan = auto_gain(ion_chambers=[ion_chamber], queue=queue, prefer=prefer)
    msgs = list(plan)
    _auto_gain.GainRecommender.assert_called_with(
        volts_min=0.5, volts_max=4.5, target_volts=target_volts
    )


@pytest.fixture()
def recommender():
    recc = _auto_gain.GainRecommender()
    return recc


def test_recommender_all_low(recommender):
    """Does the engine get the right direction when all pre-amp gains are
    too low?

    """
    # Gain sensitivity levels
    gains = np.asarray([[10, 13]])
    assert gains.shape == (1, 2)
    # Corresponding volts
    volts = np.asarray([[0.1, 0.25]])
    assert volts.shape == (1, 2)
    # Check recommendations are lower by 3
    recommender.tell_many(gains, volts)
    np.testing.assert_equal(recommender.ask(1), (13, 16))


def test_recommender_some_low(recommender):
    """Does the engine get the direction right when some pre-amp gains are
    too low and some are just right?

    """
    # Gain sensitivity levels
    gains = np.asarray([[10, 13]])
    assert gains.shape == (1, 2)
    # Corresponding volts
    volts = np.asarray([[0.1, 2.5]])
    assert volts.shape == (1, 2)
    # Check recommendations
    recommender.tell_many(gains, volts)
    np.testing.assert_equal(recommender.ask(1), (13, 14))


def test_recommender_all_high(recommender):
    """Does the engine get the direction correct when all pre-amp gains
    are too high?

    """
    # Gain sensitivity levels
    gains = np.asarray([[10, 13]])
    assert gains.shape == (1, 2)
    recommender.last_point = np.asarray([10, 13])
    # Corresponding volts
    volts = np.asarray([[4.6, 5.2]])
    assert volts.shape == (1, 2)
    # Check recommendations
    recommender.tell_many(gains, volts)
    np.testing.assert_equal(recommender.ask(1), (7, 10))


def test_recommender_some_high(recommender):
    # Gain sensitivity levels
    gains = np.asarray([[10, 13]])
    assert gains.shape == (1, 2)
    # Corresponding volts
    volts = np.asarray([[5.7, 2.5]])
    assert volts.shape == (1, 2)
    # Check recommendations
    recommender.tell_many(gains, volts)
    np.testing.assert_equal(recommender.ask(1), (7, 14))


def test_recommender_high_and_low(recommender):
    # Gain sensitivity levels
    gains = np.asarray([[10, 13]])
    assert gains.shape == (1, 2)
    # Corresponding volts
    volts = np.asarray([[5.7, 0.23]])
    assert volts.shape == (1, 2)
    # Check recommendations
    recommender.tell_many(gains, volts)
    np.testing.assert_equal(recommender.ask(1), (7, 16))


def test_recommender_fill_missing_gains(recommender):
    """If we have both high and low gains already done, will the
    recommender fill in the missing pieces."""
    gains = [
        [9],
        [12],
        [10],
        # Put in one that's really high to make sure skipped points aren't included
        [16],
    ]
    volts = [
        [0.3],
        [5.2],
        [1.5],
        # Put in one that's really high to make sure skipped points aren't included
        [7.0],
    ]
    recommender.tell_many(gains, volts)
    # Does it recommend the missing gain value?
    df = recommender.dfs[0]
    assert recommender.next_gain(df) == 11


def test_recommender_no_high(recommender):
    """If the gain happens to be in range first try, we need to get
    more data to be sure we have the best point.

    """
    gains = [[8], [9], [10]]
    volts = [[0.3], [1.25], [2.7]]
    recommender.tell_many(gains, volts)
    df = recommender.dfs[0]
    assert recommender.next_gain(df) == 11


def test_recommender_no_low(recommender):
    """If the gain happens to be in range first try, we need to get
    more data to be sure we have the best point.

    """
    gains = [[8], [9], [10]]
    volts = [[1.25], [2.75], [5.4]]
    recommender.tell_many(gains, volts)
    df = recommender.dfs[0]
    assert recommender.next_gain(df) == 7


def test_recommender_no_solution(recommender):
    """If the gain profile goes from too low to too high in one step, what should we report?"""
    gains = [[9], [10]]
    volts = [[0.3], [5.2]]
    recommender.tell_many(gains, volts)
    # Does it recommend the missing gain value?
    df = recommender.dfs[0]
    assert recommender.next_gain(df) == 9


@pytest.mark.parametrize("target_volts,gain", [(0.5, 10), (2.5, 9), (4.5, 8)])
def test_recommender_correct_solution(target_volts, gain):
    """If the gain profile goes from too low to too high in one step, what should we report?"""
    recommender = _auto_gain.GainRecommender(target_volts=target_volts)
    gains = [[7], [8], [9], [10], [11]]
    volts = [[5.2], [4.1], [2.7], [1.25], [0.4]]
    recommender.tell_many(gains, volts)
    # Does it recommend the missing gain value?
    df = recommender.dfs[0]
    assert recommender.next_gain(df) == gain


def test_recommender_gain_range_high(recommender):
    """Check that the recommender doesn't go outside the allowed range."""
    gains = [[27]]
    volts = [[0.3]]
    recommender.tell_many(gains, volts)
    # Does it recommend the missing gain value?
    df = recommender.dfs[0]
    assert recommender.next_gain(df) == 27


def test_recommender_gain_range_low(recommender):
    """Check that the recommender doesn't go outside the allowed range."""
    gains = [[0]]
    volts = [[5.4]]
    recommender.tell_many(gains, volts)
    # Does it recommend the missing gain value?
    df = recommender.dfs[0]
    assert recommender.next_gain(df) == 0


def test_recommender_no_change(recommender):
    """If we've already found the best solution, we should stop the scan."""
    # Set a history of gain measurements
    gains = np.asarray(
        [
            [10, 13],
            [11, 11],
            [12, 14],
            [13, 12],
        ]
    )
    volts = np.asarray(
        [
            [7.10, 2.23],
            [4.30, 5.30],
            [2.10, 0.10],
            [0.20, 4.33],
        ]
    )
    recommender.tell_many(gains, volts)
    # Make sure the engine recommends the best solution
    assert recommender.ask(1) == [12, 13]
    # Pass in results for this new measurement
    recommender.tell_many([[12, 13]], [[2.13, 2.19]])
    # Check recommendations
    with pytest.raises(NoRecommendation):
        recommender.ask(1)
