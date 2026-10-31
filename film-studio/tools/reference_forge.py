"""CLI kreatora referencji V8.7. Przykłady:
  python -m tools.reference_forge create character "Ona" "opis..." --style realistic --src a.png --src b.png
  python -m tools.reference_forge anchor ona --cands 3     # kandydaci na widok główny
  python -m tools.reference_forge approve ona front_a --viewed   # po obejrzeniu obrazu (potwierdza człowiek)
  python -m tools.reference_forge set ona                  # pozostałe widoki na bazie kotwicy
  python -m tools.reference_forge sheet ona                # plansza kontaktowa
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import reference_forge_v87 as F  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('create')
    c.add_argument('kind', choices=['character', 'location']); c.add_argument('name'); c.add_argument('description')
    c.add_argument('--style', default='realistic', choices=list(F.STYLES)); c.add_argument('--src', action='append', default=[]); c.add_argument('--extra', default='')
    a = sub.add_parser('anchor'); a.add_argument('id'); a.add_argument('--cands', type=int, default=3)
    p = sub.add_parser('approve'); p.add_argument('id'); p.add_argument('image')
    p.add_argument('--viewed', action='store_true', help='potwierdzam, że obraz obejrzałem')
    s = sub.add_parser('set'); s.add_argument('id'); s.add_argument('--cands', type=int, default=1); s.add_argument('--views', default='')
    sh = sub.add_parser('sheet'); sh.add_argument('id')
    sub.add_parser('list')
    m = sub.add_parser('manifest'); m.add_argument('id')
    x = ap.parse_args(argv)
    if x.cmd == 'create':
        print(json.dumps(F.public_view(F.create(x.kind, x.name, x.description, x.style, x.src, x.extra)), ensure_ascii=False))
    elif x.cmd == 'anchor':
        meta = F._load(x.id)
        print(F.generate(x.id, [F.ANCHOR[meta['kind']]], cands=x.cands))
    elif x.cmd == 'approve':
        F.approve(x.id, x.image, viewed_confirmed=x.viewed)
        print('zatwierdzono', x.image)
    elif x.cmd == 'set':
        meta = F._load(x.id)
        ids = [v for v in x.views.split(',') if v] or [v[0] for v in F.views_for(meta['kind']) if v[0] != F.ANCHOR[meta['kind']]]
        print(F.generate(x.id, ids, cands=x.cands))
    elif x.cmd == 'sheet':
        print(F.contact_sheet(x.id))
    elif x.cmd == 'list':
        print(json.dumps(F.list_all(), ensure_ascii=False, indent=1))
    elif x.cmd == 'manifest':
        print(json.dumps(F.manifest(x.id), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
