# -*- coding: utf-8 -*-
"""Read-only Nachbau des geplanten AST-Sweeps aus Plan 01 Task 2 (Pruefzwecke, wird danach geloescht)."""
import ast, pathlib, re, sys

REPO = pathlib.Path(r"C:\Users\andre\dev\salesnerve")
ROUTES = sorted((REPO / "routes").glob("*.py"))

HELFER = ('sid_belongs_to', 'resolve_own_sid_by_call_id', 'call_belongs_to')
SERVER_IDENTITAET = ('g.user.id', 'g.org.id', 'g.tenant_id', 'g.user.org_id')
ANERKANNT = {'sid_belongs_to', 'resolve_own_sid_by_call_id', 'call_belongs_to', '_require_own_profile'}
KENNUNGEN = {'sid', 'call_id', 'profile_id'}

def own_nodes(fn):
    out = []
    def rec(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            out.append(child)
            rec(child)
    rec(fn)
    return out

def analyse(src, rel):
    tree = ast.parse(src)
    mengen = {k: [] for k in ('ZUSTAND','SID','CALLID','PROFILEID','URL')}
    details = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        nodes = own_nodes(fn)
        name = f"{rel}::{fn.name}:{fn.lineno}"
        # Menge 1
        hit_state = any(
            (isinstance(n, ast.Attribute) and n.attr == '_session_state') or
            (isinstance(n, ast.Name) and n.id == '_session_state')
            for n in nodes)
        # Mengen 2-4
        get_keys = set()
        for n in nodes:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'get':
                if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    get_keys.add(n.args[0].value)
        # Menge 5
        url_hit = False
        argnames = {a.arg for a in fn.args.args}
        for dec in fn.decorator_list:
            if isinstance(dec, ast.Call):
                for d in ast.walk(dec):
                    if isinstance(d, ast.Constant) and isinstance(d.value, str):
                        for var in re.findall(r'<(?:[^:<>]+:)?([A-Za-z_][A-Za-z0-9_]*)>', d.value):
                            if var in KENNUNGEN and var in argnames:
                                url_hit = True
        # Regel-Bausteine
        helfer_calls = set()
        for n in nodes:
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Name) and n.func.id in ANERKANNT:
                    helfer_calls.add(n.func.id)
                if isinstance(n.func, ast.Attribute) and n.func.attr in ANERKANNT:
                    helfer_calls.add(n.func.attr)
        server_id = any(
            isinstance(n, ast.Attribute) and ast.unparse(n) in SERVER_IDENTITAET
            for n in nodes)
        # org_id-Bindung eng: (a) Compare
        org_a = False
        for n in nodes:
            if isinstance(n, ast.Compare):
                seiten = [n.left] + list(n.comparators)
                hat_org = any(isinstance(s, ast.Attribute) and s.attr == 'org_id' for s in seiten)
                hat_gid = any(isinstance(s, ast.Attribute) and ast.unparse(s) in SERVER_IDENTITAET for s in seiten)
                if hat_org and hat_gid:
                    org_a = True
        # (b) Lese-/Filter-Aufruf mit kw org_id=<server-id>; NICHT Konstruktoren
        org_b = False
        for n in nodes:
            if isinstance(n, ast.Call):
                fname = None
                if isinstance(n.func, ast.Attribute):
                    fname = n.func.attr
                if fname in ('filter_by', 'filter', 'get'):
                    for kw in n.keywords:
                        if kw.arg == 'org_id' and isinstance(kw.value, ast.Attribute) \
                           and ast.unparse(kw.value) in SERVER_IDENTITAET:
                            org_b = True
        details[name] = dict(helfer=sorted(helfer_calls), server_id=server_id,
                             org_a=org_a, org_b=org_b, get_keys=sorted(get_keys & KENNUNGEN))
        if hit_state: mengen['ZUSTAND'].append(name)
        if 'sid' in get_keys: mengen['SID'].append(name)
        if 'call_id' in get_keys: mengen['CALLID'].append(name)
        if 'profile_id' in get_keys: mengen['PROFILEID'].append(name)
        if url_hit: mengen['URL'].append(name)
    return mengen, details

alle = {k: [] for k in ('ZUSTAND','SID','CALLID','PROFILEID','URL')}
alle_details = {}
for p in ROUTES:
    rel = f"routes/{p.name}"
    m, d = analyse(p.read_text(encoding='utf-8'), rel)
    for k in alle: alle[k].extend(m[k])
    alle_details.update(d)

print("=== MENGEN (roh, ungefixter Stand) ===")
for k, v in alle.items():
    print(f"\n{k}  ({len(v)}):")
    for name in v:
        det = alle_details[name]
        print(f"  {name}  helfer={det['helfer']} server_id={det['server_id']} org_a={det['org_a']} org_b={det['org_b']}")

print("\n=== URTEIL Menge 4 (PROFILEID) nach enger org_id-Regel ===")
for name in alle['PROFILEID']:
    det = alle_details[name]
    ok = det['org_a'] or det['org_b'] or bool(set(det['helfer']))
    print(f"  {'GRUEN' if ok else 'ROT  '}  {name}  (a={det['org_a']} b={det['org_b']} helfer={det['helfer']})")

print("\n=== URTEIL Menge 5 (URL) ===")
for name in alle['URL']:
    det = alle_details[name]
    ok = det['server_id'] or bool(set(det['helfer']))
    print(f"  {'GRUEN' if ok else 'ROT  '}  {name}  (server_id={det['server_id']} helfer={det['helfer']})")
