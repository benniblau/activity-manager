"""Tests for moving planned activities between days (cross-day drag & drop)"""

import pytest

from app.repositories import PlannedActivityRepository


USER_ID = 1
OTHER_USER_ID = 2


@pytest.fixture
def plan_db(app, db):
    """Clean planned_activities before each test"""
    db.execute('DELETE FROM planned_activities')
    db.commit()
    with app.app_context():
        yield db


def _create(repo, day_date, user_id=USER_ID, **kwargs):
    data = {
        'user_id': user_id,
        'day_date': day_date,
        'sport_type': None,
        'notes': kwargs.pop('notes', None),
    }
    data.update(kwargs)
    return repo.create(data)


def _day_state(repo, day_date, user_id=USER_ID):
    rows = repo.fetchall(
        '''SELECT id, sort_order FROM planned_activities
           WHERE user_id = ? AND day_date = ? ORDER BY sort_order''',
        (user_id, day_date)
    )
    return [(r['id'], r['sort_order']) for r in rows]


def test_move_to_other_day_reorders_both_days(app, plan_db):
    with app.app_context():
        repo = PlannedActivityRepository()
        mon_a = _create(repo, '2026-08-10', notes='mon-a')
        mon_b = _create(repo, '2026-08-10', notes='mon-b')
        tue_a = _create(repo, '2026-08-11', notes='tue-a')

        # Drag mon_a to Tuesday, dropping it above tue_a
        result = repo.move_to_day(
            mon_a, USER_ID, '2026-08-11',
            to_ordered_ids=[mon_a, tue_a],
            from_day='2026-08-10',
            from_ordered_ids=[mon_b],
        )

        assert result['day_date'] == '2026-08-11'
        assert _day_state(repo, '2026-08-11') == [(mon_a, 0), (tue_a, 1)]
        assert _day_state(repo, '2026-08-10') == [(mon_b, 0)]


def test_move_clears_match_from_another_day(app, plan_db):
    with app.app_context():
        plan_db.execute(
            '''INSERT INTO activities
                   (id, name, day_date, sport_type, start_date, start_date_local, elapsed_time)
               VALUES (900, 'Monday run', '2026-08-10', 'Run',
                       '2026-08-10T08:00:00Z', '2026-08-10T10:00:00', 3600)'''
        )
        plan_db.commit()

        repo = PlannedActivityRepository()
        plan_id = _create(repo, '2026-08-10', matched_activity_id=900)

        result = repo.move_to_day(
            plan_id, USER_ID, '2026-08-12',
            to_ordered_ids=[plan_id],
            from_day='2026-08-10',
            from_ordered_ids=[],
        )

        assert result['matched_activity_id'] is None
        row = repo.fetchone(
            'SELECT day_date, matched_activity_id FROM planned_activities WHERE id = ?',
            (plan_id,)
        )
        assert row['day_date'] == '2026-08-12'
        assert row['matched_activity_id'] is None


def test_move_keeps_match_when_activity_is_on_target_day(app, plan_db):
    with app.app_context():
        plan_db.execute(
            '''INSERT INTO activities
                   (id, name, day_date, sport_type, start_date, start_date_local, elapsed_time)
               VALUES (901, 'Wednesday run', '2026-08-12', 'Run',
                       '2026-08-12T08:00:00Z', '2026-08-12T10:00:00', 3600)'''
        )
        plan_db.commit()

        repo = PlannedActivityRepository()
        plan_id = _create(repo, '2026-08-10', matched_activity_id=901)

        result = repo.move_to_day(
            plan_id, USER_ID, '2026-08-12',
            to_ordered_ids=[plan_id],
            from_day='2026-08-10',
            from_ordered_ids=[],
        )

        assert result['matched_activity_id'] == 901


def test_move_rejects_plan_of_another_user(app, plan_db):
    with app.app_context():
        repo = PlannedActivityRepository()
        plan_id = _create(repo, '2026-08-10', user_id=OTHER_USER_ID)

        assert repo.move_to_day(plan_id, USER_ID, '2026-08-11') is None

        row = repo.fetchone(
            'SELECT day_date FROM planned_activities WHERE id = ?', (plan_id,)
        )
        assert row['day_date'] == '2026-08-10'


def test_reorder_ignores_ids_from_another_day(app, plan_db):
    with app.app_context():
        repo = PlannedActivityRepository()
        mon = _create(repo, '2026-08-10')
        tue = _create(repo, '2026-08-11')

        repo.reorder('2026-08-10', USER_ID, [tue, mon])

        # tue is untouched; mon keeps its own day's ordering
        assert _day_state(repo, '2026-08-11') == [(tue, 0)]
        assert _day_state(repo, '2026-08-10') == [(mon, 1)]
