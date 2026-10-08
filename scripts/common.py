"""Shared config/paths. Everything is relative to the repo root so the repo can be cloned anywhere."""
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _load():
    p = os.path.join(ROOT, 'config.yaml')
    try:
        import yaml
        return yaml.safe_load(open(p))
    except ImportError:  # minimal fallback: config is also readable as JSON-ish defaults
        raise SystemExit('PyYAML is required: pip install -r requirements.txt')
CFG = _load()
def path(key): return os.path.join(ROOT, CFG['paths'][key])
def rel(*parts): return os.path.join(ROOT, *parts)
def load_jsonl(p): return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
def write_jsonl(p, rows):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
def load_rules():
    import glob
    return {r['id']: r for f in sorted(glob.glob(os.path.join(ROOT, CFG['paths']['rules_dir'], '[a-e]_*.json'))) for r in json.load(open(f))['rules']}
