from collections import Counter
from uuid import UUID, uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.modules.seating.engine import G, Rule, SeatingError, T, check, solve


def family(size, group=None, side="both", kids=0):
    hid = uuid4()
    return [G(uuid4(), hid, "adult", group, side) for _ in range(size)] + [
        G(uuid4(), hid, "child", group, side) for _ in range(kids)
    ]


def tables(*caps, kind="regular"):
    return [T(uuid4(), kind, c, f"{kind} {i}") for i, c in enumerate(caps, 1)]


def pair(a: UUID, b: UUID, kind: str) -> Rule:
    a, b = sorted([a, b])
    return Rule(kind, a, b)


def errors(guests, tabs, rules, assignment):
    return [i.code for i in check(guests, tabs, rules, assignment) if i.severity == "error"]


def test_groups_and_families_together():
    work = family(2, "praca") + family(2, "praca") + family(1, "praca")
    fam = family(3, "rodzina") + family(2, "rodzina")
    guests = work + fam
    tabs = tables(5, 5, 5)
    r = solve(guests, tabs, [], {})
    assert len({r.assignment[g.id] for g in work}) == 1
    assert len({r.assignment[g.id] for g in fam}) == 1
    assert check(guests, tabs, [], r.assignment) == []


def test_apart_and_together_rules():
    a, b, c = family(1), family(1), family(1)
    guests = a + b + c
    tabs = tables(3, 3)
    rules = [pair(a[0].id, b[0].id, "apart"), pair(a[0].id, c[0].id, "together")]
    r = solve(guests, tabs, rules, {})
    assert r.assignment[a[0].id] != r.assignment[b[0].id]
    assert r.assignment[a[0].id] == r.assignment[c[0].id]
    assert errors(guests, tabs, rules, r.assignment) == []


def test_apart_inside_household_splits_it():
    fam = family(2)
    tabs = tables(4, 4)
    rules = [pair(fam[0].id, fam[1].id, "apart")]
    r = solve(fam, tabs, rules, {})
    assert r.assignment[fam[0].id] != r.assignment[fam[1].id]
    assert r.split_households == [fam[0].household_id]


def test_locked_guest_stays_and_pulls_family():
    fam = family(3)
    other = family(2)
    tabs = tables(5, 5)
    locked = {fam[0].id: tabs[1].id}
    r = solve(fam + other, tabs, [], locked)
    assert {r.assignment[g.id] for g in fam} == {tabs[1].id}


def test_head_table_not_filled_automatically():
    head = tables(4, kind="head")
    tabs = head + tables(6)
    guests = family(2) + family(3)
    r = solve(guests, tabs, [], {})
    assert head[0].id not in r.assignment.values()


def test_children_to_kids_table_without_split_warning():
    guests = family(2, kids=2) + family(2, kids=1)
    kids = tables(4, kind="kids")
    tabs = tables(6) + kids
    r = solve(guests, tabs, [], {})
    children = [g for g in guests if g.age_group == "child"]
    assert {r.assignment[g.id] for g in children} == {kids[0].id}
    assert check(guests, tabs, [], r.assignment) == []
    with pytest.raises(SeatingError) as e:  # bez stołu dziecięcego 7 osób nie zmieści się w 6
        solve(guests, tabs, [], {}, kids_table=False)
    assert e.value.code == "seating.capacity_insufficient"
    roomy = tables(8) + kids
    off = solve(guests, roomy, [], {}, kids_table=False)
    assert kids[0].id not in off.assignment.values()


def test_household_bigger_than_any_table_is_split_with_warning():
    big = family(7)
    tabs = tables(4, 4)
    r = solve(big, tabs, [], {})
    assert Counter(r.assignment.values()) == Counter({tabs[0].id: 4, tabs[1].id: 3}) or Counter(
        r.assignment.values()
    ) == Counter({tabs[0].id: 3, tabs[1].id: 4})
    assert [i.code for i in check(big, tabs, [], r.assignment)] == ["household_split"]


def test_errors_capacity_locked_infeasible():
    guests = family(3)
    with pytest.raises(SeatingError) as e:
        solve(guests, tables(2), [], {})
    assert e.value.code == "seating.capacity_insufficient"
    tabs = tables(1, 5)
    with pytest.raises(SeatingError) as e:
        solve(guests, tabs, [], {guests[0].id: tabs[0].id, guests[1].id: tabs[0].id})
    assert e.value.code == "seating.locked_over_capacity"
    a, b, c = family(1), family(1), family(1)
    rules = [pair(a[0].id, b[0].id, "together"), pair(b[0].id, c[0].id, "together")]
    with pytest.raises(SeatingError) as e:
        solve(a + b + c, tables(2, 2), rules, {})
    assert e.value.code == "seating.infeasible"


def test_deterministic():
    guests = [g for i in range(12) for g in family(1 + i % 3, f"grupa {i % 4}", "bride")]
    tabs = tables(8, 8, 8, 8)
    assert solve(guests, tabs, [], {}).assignment == solve(guests, tabs, [], {}).assignment


def test_check_reports_problems():
    adult, kid = family(1), family(0, kids=1)
    declined = [G(uuid4(), uuid4(), attending=False, name="Ola")]
    kids = tables(1, kind="kids")
    small = tables(1)
    guests = adult + kid + declined
    assignment = {adult[0].id: kids[0].id, kid[0].id: kids[0].id, declined[0].id: small[0].id}
    codes = {i.code for i in check(guests, kids + small, [], assignment)}
    assert codes == {"over_capacity", "adult_at_kids_table", "not_attending_seated"}


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(st.integers(1, 4), min_size=1, max_size=10),
    st.lists(st.integers(2, 8), min_size=1, max_size=4),
    st.lists(st.tuples(st.integers(0, 30), st.integers(0, 30), st.booleans()), max_size=4),
)
def test_solution_respects_hard_constraints(sizes, caps, raw_rules):
    guests = [g for i, s in enumerate(sizes) for g in family(s, f"g{i % 3}")]
    tabs = tables(*caps)
    rules = []
    seen = set()
    for i, j, apart in raw_rules:
        a, b = guests[i % len(guests)].id, guests[j % len(guests)].id
        if a != b and frozenset((a, b)) not in seen:
            seen.add(frozenset((a, b)))
            rules.append(pair(a, b, "apart" if apart else "together"))
    try:
        r = solve(guests, tabs, rules, {}, time_limit=2)
    except SeatingError as e:
        code = e.code
        r = None
    if r is None:
        assert code in {"seating.capacity_insufficient", "seating.infeasible"}
        return
    assert set(r.assignment) == {g.id for g in guests}
    assert errors(guests, tabs, rules, r.assignment) == []


def test_teens_at_kids_table_only_when_asked_and_after_children():
    hid = uuid4()
    parents = [G(uuid4(), hid, "adult"), G(uuid4(), hid, "adult")]
    child, teen = G(uuid4(), hid, "child"), G(uuid4(), hid, "teen")
    guests = [*parents, child, teen]
    regular = tables(6)
    two = tables(2, kind="kids")
    # Domyślnie nastolatek zostaje z rodzicami.
    r = solve(guests, regular + two, [], {})
    assert r.assignment[child.id] == two[0].id
    assert r.assignment[teen.id] == regular[0].id
    # Na życzenie: także nastolatek przy stole dziecięcym.
    r = solve(guests, regular + two, [], {}, kids_table_teens=True)
    assert r.assignment[teen.id] == two[0].id
    assert check(guests, regular + two, [], r.assignment) == []
    # Jedno miejsce: pierwszeństwo ma młodsze dziecko.
    one = tables(1, kind="kids")
    r = solve(guests, regular + one, [], {}, kids_table_teens=True)
    assert r.assignment[child.id] == one[0].id
    assert r.assignment[teen.id] == regular[0].id
