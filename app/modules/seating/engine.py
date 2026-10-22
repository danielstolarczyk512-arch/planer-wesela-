"""Plan stołów: kontrola poprawności i automatyczne usadzenie (OR-Tools CP-SAT, Apache-2.0).

Czysta logika bez bazy danych. Zasady:
- gość siedzi przy jednym stole, stół ma pojemność, stół pary młodej (`head`) automat pomija;
- gospodarstwo (rodzina z jednego zaproszenia) siedzi razem; jeśli jest stół dziecięcy,
  dzieci (bez nastolatków) trafiają tam, dopóki starczy miejsc (reszta zostaje z rodzicami);
- reguły pary „razem” i „osobno” są twarde, ręczne przypisania (`locked`) nienaruszalne;
- cel: jak najmniej rozbitych grup (etykieta grupy, np. „praca Ani”; strona panny/pana młodego)
  i możliwie mało zajętych stołów.

Wydajność: rodziny o tych samych cechach (grupa, strona, liczba osób) są wymienne, więc model
liczy je zbiorczo (zmienne całkowite „ile takich rodzin przy stole”), a identyczne stoły mają
uporządkowane obciążenie. Bez tego solver tonie w symetriach. Wynik jest deterministyczny.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import pairwise
from uuid import UUID

from ortools.sat.python import cp_model

CHILDREN = frozenset({"child", "teen"})
W_HOUSEHOLD = 20  # rozbite gospodarstwo (np. większe niż stół)
W_GROUP = 10
W_SIDE = 2
W_TABLE_USED = 1
W_NEAR = 3  # za każdy „stopień” odległości stołu od celu (dla grup „blisko”)


@dataclass(frozen=True)
class G:
    id: UUID
    household_id: UUID
    age_group: str = "adult"
    group: str | None = None
    side: str = "both"
    attending: bool = True
    name: str = ""


@dataclass(frozen=True)
class T:
    id: UUID
    kind: str
    capacity: int
    name: str = ""


@dataclass(frozen=True)
class Rule:
    kind: str  # together | apart
    a: UUID
    b: UUID


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    guest_ids: tuple[UUID, ...]
    table_ids: tuple[UUID, ...]
    message: str


@dataclass
class Result:
    status: str  # optimal | feasible
    assignment: dict[UUID, UUID]
    split_households: list[UUID] = field(default_factory=list)


class SeatingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _group_key(g: G) -> str | None:
    return " ".join(g.group.lower().split()) if g.group else None


# --- kontrola ------------------------------------------------------------------------


def check(
    guests: list[G], tables: list[T], rules: list[Rule], assignment: dict[UUID, UUID]
) -> list[Issue]:
    by_id = {g.id: g for g in guests}
    tables_by_id = {t.id: t for t in tables}
    issues: list[Issue] = []
    seated: dict[UUID, list[UUID]] = defaultdict(list)
    for gid, tid in assignment.items():
        seated[tid].append(gid)
    for t in tables:
        if len(seated[t.id]) > t.capacity:
            issues.append(
                Issue(
                    "over_capacity",
                    "error",
                    tuple(seated[t.id]),
                    (t.id,),
                    f"Przy stole „{t.name}” jest {len(seated[t.id])} osób na {t.capacity} miejsc.",
                )
            )
        if t.kind == "kids":
            adults = [g for g in seated[t.id] if g in by_id and by_id[g].age_group not in CHILDREN]
            if adults:
                issues.append(
                    Issue(
                        "adult_at_kids_table",
                        "warning",
                        tuple(adults),
                        (t.id,),
                        f"Przy stole dziecięcym „{t.name}” siedzą dorośli.",
                    )
                )
    for r in rules:
        ta, tb = assignment.get(r.a), assignment.get(r.b)
        if ta is None or tb is None:
            continue
        if r.kind == "apart" and ta == tb:
            issues.append(
                Issue(
                    "apart_broken",
                    "error",
                    (r.a, r.b),
                    (ta,),
                    "Osoby, które mają siedzieć osobno, są przy jednym stole.",
                )
            )
        if r.kind == "together" and ta != tb:
            issues.append(
                Issue(
                    "together_broken",
                    "error",
                    (r.a, r.b),
                    (ta, tb),
                    "Osoby, które mają siedzieć razem, są przy różnych stołach.",
                )
            )
    households: dict[UUID, list[G]] = defaultdict(list)
    for g in guests:
        if g.id in assignment:
            households[g.household_id].append(g)
    for members in households.values():
        at = {
            assignment[g.id]
            for g in members
            if not (g.age_group in CHILDREN and tables_by_id[assignment[g.id]].kind == "kids")
        }
        if len(at) > 1:
            issues.append(
                Issue(
                    "household_split",
                    "warning",
                    tuple(g.id for g in members),
                    tuple(sorted(at)),
                    "Rodzina z jednego zaproszenia siedzi przy różnych stołach.",
                )
            )
    for g in guests:
        if g.id in assignment and not g.attending:
            issues.append(
                Issue(
                    "not_attending_seated",
                    "warning",
                    (g.id,),
                    (assignment[g.id],),
                    f"{g.name or 'Gość'} ma miejsce przy stole, ale odmówił(a) udziału.",
                )
            )
    return issues


# --- automatyczne usadzenie --------------------------------------------------------------


@dataclass
class _Unit:
    """Osoby, które muszą siedzieć razem (rodzina albo pojedynczy gość)."""

    members: list[G]
    allowed: list[UUID]
    special: bool  # reguła lub wymuszony stół: nie łączymy z innymi w typ zbiorczy
    household: UUID | None = None  # rozbite gospodarstwo: klaster o wysokiej wadze

    @property
    def size(self) -> int:
        return len(self.members)

    def key(self) -> tuple[object, ...]:
        g = self.members[0]
        if self.special:
            return ("unit", g.id)
        return (_group_key(g), g.side, self.size, self.household, tuple(self.allowed))


def _kids_to_kids_tables(
    guests: list[G],
    tables: list[T],
    free: dict[UUID, int],
    locked: dict[UUID, UUID],
    ages: frozenset[str] = frozenset({"child"}),
) -> dict[UUID, UUID]:
    """Dzieci (opcjonalnie też nastolatki) przy stołach dziecięcych: najpierw młodsze, kolejno
    wg gospodarstw (rodzeństwo obok siebie). Gdy miejsc brakuje, starsi zostają z rodzicami."""
    out: dict[UUID, UUID] = {}
    kids_tables = [t for t in tables if t.kind == "kids"]
    children = sorted(
        (g for g in guests if g.age_group in ages and g.id not in locked),
        key=lambda g: (g.age_group != "child", str(g.household_id), str(g.id)),
    )
    for t in kids_tables:
        while free[t.id] > 0 and children:
            out[children.pop(0).id] = t.id
            free[t.id] -= 1
    return out


def _units(
    guests: list[G],
    tables: list[T],
    rules: list[Rule],
    fixed: dict[UUID, UUID],
    keep_households: bool,
) -> tuple[list[_Unit], list[UUID]]:
    regular = [t.id for t in tables if t.kind == "regular"]
    regular_or_head = {t.id for t in tables if t.kind != "kids"}
    max_regular = max((t.capacity for t in tables if t.kind == "regular"), default=0)
    in_rules = {gid for r in rules for gid in (r.a, r.b)}
    hh_of = {g.id: g.household_id for g in guests}
    apart_inside = {
        hh_of[r.a]
        for r in rules
        if r.kind == "apart" and r.a in hh_of and hh_of.get(r.a) == hh_of.get(r.b)
    }
    households: dict[UUID, list[G]] = defaultdict(list)
    anchors: dict[UUID, set[UUID]] = defaultdict(set)
    for g in sorted(guests, key=lambda g: str(g.id)):
        if g.id not in fixed:
            households[g.household_id].append(g)
        elif fixed[g.id] in regular_or_head:
            anchors[g.household_id].add(fixed[g.id])  # stół dziecięcy nie wiąże rodziny

    units: list[_Unit] = []
    split: list[UUID] = []
    for hid in sorted(households, key=str):
        members = households[hid]
        forced = sorted(anchors[hid]) if keep_households and len(anchors[hid]) == 1 else None
        whole = keep_households and hid not in apart_inside
        if whole and len(members) > max_regular and not forced:
            whole = False
        if keep_households and not whole and len(members) > 1:
            split.append(hid)
        groups = [members] if whole else [[g] for g in members]
        for part in groups:
            special = bool(forced) or any(g.id in in_rules for g in part)
            units.append(
                _Unit(
                    part,
                    forced or regular,
                    special,
                    household=hid if hid in split else None,
                )
            )
    return units, split


def _greedy_hint(
    type_list: list[list[_Unit]],
    tables: list[T],
    free: dict[UUID, int],
    classes: dict[tuple[str, int], list[UUID]],
) -> dict[tuple[int, UUID], int]:
    """Szybkie rozwiązanie startowe: grupa po grupie, największe rodziny najpierw, stoły
    zapełniane po kolei. Solver je poprawia (i naprawia, jeśli łamie reguły)."""
    left = {t.id: free[t.id] for t in tables if t.kind == "regular"}
    order = [t.id for t in tables if t.kind == "regular"]
    by_group: dict[object, list[int]] = defaultdict(list)
    for k, us in enumerate(type_list):
        by_group[_group_key(us[0].members[0]) or ""].append(k)
    groups = sorted(
        by_group.values(),
        key=lambda ks: (-sum(len(type_list[k]) * type_list[k][0].size for k in ks), ks[0]),
    )
    content: dict[UUID, list[int]] = defaultdict(list)
    for ks in groups:
        units = sorted(
            ((k, u.size) for k in ks for u in type_list[k]), key=lambda ku: (-ku[1], ku[0])
        )
        for k, size in units:
            allowed = set(type_list[k][0].allowed)
            tid = next(
                (t for t in order if t in allowed and left[t] >= size),
                next((t for t in type_list[k][0].allowed), None),
            )
            if tid is None:
                continue
            content[tid].append(k)
            left[tid] = left.get(tid, 0) - size
    # identyczne stoły: najpełniejszy pierwszy (zgodnie z ograniczeniem symetrii)
    for ids in classes.values():
        bins = sorted(
            (content.get(t, []) for t in ids),
            key=lambda ks: -sum(type_list[k][0].size for k in ks),
        )
        for t, ks in zip(ids, bins, strict=True):
            content[t] = ks
    hint: dict[tuple[int, UUID], int] = defaultdict(int)
    for tid, ks in content.items():
        for k in ks:
            hint[k, tid] += 1
    return hint


def solve(
    guests: list[G],
    tables: list[T],
    rules: list[Rule],
    locked: dict[UUID, UUID],
    *,
    keep_households: bool = True,
    kids_table: bool = True,
    kids_table_teens: bool = False,
    time_limit: float = 10.0,
    table_rank: dict[UUID, int] | None = None,
    near_groups: frozenset[str] = frozenset(),
) -> Result:
    """Usadza gości spoza `locked`. Zwraca pełne przypisanie (razem z `locked`)."""
    tables_by_id = {t.id: t for t in tables}
    free = {t.id: t.capacity for t in tables}
    for tid in locked.values():
        free[tid] -= 1
    full = [tables_by_id[tid].name for tid, c in free.items() if c < 0]
    if full:
        raise SeatingError(
            "seating.locked_over_capacity",
            f"Ręcznie usadzonych osób jest więcej niż miejsc przy: {', '.join(sorted(full))}.",
        )
    to_seat = [g for g in guests if g.id not in locked]
    kids_seats = sum(c for tid, c in free.items() if tables_by_id[tid].kind == "kids")
    kid_ages = frozenset({"child", "teen"}) if kids_table_teens else frozenset({"child"})
    children = sum(1 for g in to_seat if g.age_group in kid_ages)
    seats = sum(c for tid, c in free.items() if tables_by_id[tid].kind == "regular") + (
        min(kids_seats, children) if kids_table else 0
    )
    if len(to_seat) > seats:
        raise SeatingError(
            "seating.capacity_insufficient",
            f"Do usadzenia jest {len(to_seat)} osób, a wolnych miejsc {seats}. "
            "Dodaj stół albo zwiększ liczbę miejsc.",
        )
    fixed = dict(locked)
    if kids_table:
        fixed |= _kids_to_kids_tables(guests, tables, free, locked, kid_ages)
    units, split = _units(guests, tables, rules, fixed, keep_households)
    if not units:
        return Result("optimal", fixed, split)

    # typy zbiorcze: wymienne jednostki liczymy razem
    types: dict[tuple[object, ...], list[_Unit]] = defaultdict(list)
    for u in units:
        types[u.key()].append(u)
    type_list = list(types.values())

    m = cp_model.CpModel()
    n: dict[tuple[int, UUID], cp_model.IntVar] = {}
    for k, us in enumerate(type_list):
        for tid in us[0].allowed:
            n[k, tid] = m.new_int_var(0, len(us), f"n{k}_{tid.hex[:6]}")
        m.add(sum(n[k, tid] for tid in us[0].allowed) == len(us))
    load: dict[UUID, cp_model.LinearExprT] = {}
    for t in tables:
        terms = [type_list[k][0].size * v for (k, tid), v in n.items() if tid == t.id]
        if terms:
            load[t.id] = sum(terms)
            m.add(load[t.id] <= free[t.id])

    # symetria: identyczne, puste stoły uporządkowane wg obciążenia
    occupied = set(fixed.values())
    classes: dict[tuple[str, int], list[UUID]] = defaultdict(list)
    for t in tables:
        if t.id in load and t.id not in occupied:
            classes[t.kind, t.capacity].append(t.id)
    for ids in classes.values():
        for a, b in pairwise(ids):
            m.add(load[a] >= load[b])

    type_of: dict[UUID, int] = {
        g.id: k for k, us in enumerate(type_list) for u in us for g in u.members
    }

    def var(gid: UUID, tid: UUID) -> cp_model.LinearExprT | int:
        if gid in fixed:
            return 1 if fixed[gid] == tid else 0
        return n.get((type_of[gid], tid), 0)

    for r in rules:
        if not all(g in fixed or g in type_of for g in (r.a, r.b)):
            continue
        for t in tables:
            va, vb = var(r.a, t.id), var(r.b, t.id)
            if isinstance(va, int) and isinstance(vb, int):
                continue  # obie osoby przypisane na stałe: ewentualny problem pokaże kontrola
            if r.kind == "apart":
                m.add(cp_model.LinearExpr.sum([va, vb]) <= 1)
            else:
                m.add(va == vb)

    cost: list[cp_model.LinearExprT] = []
    clusters: dict[tuple[str, object], list[int]] = defaultdict(list)
    for k, us in enumerate(type_list):
        g = us[0].members[0]
        if _group_key(g):
            clusters["group", _group_key(g)].append(k)
        if g.side in ("bride", "groom"):
            clusters["side", g.side].append(k)
        if us[0].household:
            clusters["household", us[0].household].append(k)
    weights = {"group": W_GROUP, "side": W_SIDE, "household": W_HOUSEHOLD}
    for (kind, _), members in sorted(clusters.items(), key=lambda kv: str(kv[0])):
        if sum(len(type_list[k]) for k in members) < 2:
            continue
        for t in tables:
            here = [(k, n[k, t.id]) for k in members if (k, t.id) in n]
            if not here:
                continue
            z = m.new_bool_var("")
            for k, v in here:
                m.add(v <= len(type_list[k]) * z)
            cost.append(weights[kind] * z)
    # „Blisko stołu pary / parkietu”: grupy z listy płacą za odległość stołu (ranga 0 = najbliżej).
    if table_rank and near_groups:
        for (k, tid), v in n.items():
            if _group_key(type_list[k][0].members[0]) in near_groups and tid in table_rank:
                cost.append(W_NEAR * table_rank[tid] * type_list[k][0].size * v)
    for t in tables:
        if t.id in load:
            used = m.new_bool_var("")
            m.add(load[t.id] <= free[t.id] * used)
            cost.append(W_TABLE_USED * used)
    m.minimize(sum(cost))
    for (k, tid), count in _greedy_hint(type_list, tables, free, classes).items():
        if (k, tid) in n:
            m.add_hint(n[k, tid], count)

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 8
    solver.parameters.interleave_search = True  # równolegle, ale deterministycznie
    solver.parameters.random_seed = 42
    solver.parameters.max_deterministic_time = time_limit
    solver.parameters.max_time_in_seconds = time_limit * 3
    status = solver.solve(m)
    if status == cp_model.UNKNOWN:
        raise SeatingError(
            "seating.timeout",
            "Nie udało się ułożyć planu w limicie czasu. Spróbuj ponownie z dłuższym limitem "
            "albo usadź ręcznie część gości.",
        )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SeatingError(
            "seating.infeasible",
            "Nie da się spełnić wszystkich warunków naraz. Sprawdź reguły „razem/osobno”, "
            "ręczne przypisania i liczbę miejsc przy stołach.",
        )
    assignment = dict(fixed)
    for k, us in enumerate(type_list):
        queue = list(us)
        for tid in us[0].allowed:
            for _ in range(solver.value(n[k, tid])):
                for g in queue.pop(0).members:
                    assignment[g.id] = tid
    return Result("optimal" if status == cp_model.OPTIMAL else "feasible", assignment, split)


# --- numery miejsc przy stole ------------------------------------------------------------

AGE_ORDER = {"adult": 0, "teen": 1, "child": 2, "infant": 3}


def seat_order(guests: list[G]) -> list[G]:
    """Kolejność przy stole: rodzina obok siebie — najpierw dorośli (para siedzi razem),
    potem dzieci (obok rodzica). Rodziny w kolejności nazw, deterministycznie."""
    by_household: dict[UUID, list[G]] = defaultdict(list)
    for g in guests:
        by_household[g.household_id].append(g)
    ordered: list[G] = []
    for hid in sorted(by_household, key=lambda h: (min(g.name for g in by_household[h]), str(h))):
        ordered += sorted(
            by_household[hid], key=lambda g: (AGE_ORDER.get(g.age_group, 0), g.name, str(g.id))
        )
    return ordered


def number_seats(
    guests: list[G], capacity: int, existing: dict[UUID, int] | None = None
) -> dict[UUID, int]:
    """Numery miejsc 1..capacity. Zachowuje istniejące numery (`existing`), pozostałych
    sadza kolejno w wolnych miejscach — rodzina w najdłuższym ciągłym bloku wolnych krzeseł
    (stół okrągły: miejsce `capacity` sąsiaduje z 1)."""
    existing = {gid: n for gid, n in (existing or {}).items() if 1 <= n <= capacity}
    taken = set(existing.values())
    if len(taken) != len(existing):  # zdublowane numery: zostaje pierwszy, reszta od nowa
        seen: set[int] = set()
        for gid, n in sorted(existing.items(), key=lambda kv: str(kv[0])):
            if n in seen:
                del existing[gid]
            seen.add(n)
        taken = set(existing.values())
    out = dict(existing)
    todo = [g for g in seat_order(guests) if g.id not in existing]
    free = [n for n in range(1, capacity + 1) if n not in taken]
    if len(todo) > len(free):
        raise SeatingError(
            "seating.over_capacity", "Przy stole jest więcej osób niż miejsc — zwiększ pojemność."
        )
    # Rodzinami: każda bierze kolejne wolne miejsca od początku najdłuższego wolnego ciągu.
    families: dict[UUID, list[G]] = defaultdict(list)
    for g in todo:
        families[g.household_id].append(g)
    for members in sorted(families.values(), key=lambda ms: -len(ms)):
        start = _best_run_start(free, capacity, len(members))
        idx = free.index(start)
        rotated = free[idx:] + free[:idx]
        for g, n in zip(members, rotated, strict=False):
            out[g.id] = n
            free.remove(n)
    return out


def _best_run_start(free: list[int], capacity: int, size: int) -> int:
    """Początek ciągu kolejnych wolnych miejsc (z zawinięciem stołu) — najkrótszy, który
    zmieści rodzinę; gdy żaden nie mieści, najdłuższy."""
    free_set = set(free)
    runs: list[tuple[int, int]] = []  # (początek, długość)
    for n in free:
        prev = capacity if n == 1 else n - 1
        if prev in free_set and len(free_set) < capacity:
            continue  # nie jest początkiem ciągu
        length, cur = 0, n
        while cur in free_set and length < capacity:
            length += 1
            cur = 1 if cur == capacity else cur + 1
        runs.append((n, length))
    if not runs:
        return free[0]
    fitting = [r for r in runs if r[1] >= size]
    if fitting:
        return min(fitting, key=lambda r: (r[1], r[0]))[0]
    return max(runs, key=lambda r: (r[1], -r[0]))[0]
