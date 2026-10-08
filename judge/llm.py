"""Minimal OpenAI-compatible chat clients (xAI, OpenRouter). Keys are read at runtime and never logged or written.
OpenRouter key: loaded from ~/.config/openrouter/api_key into OPENROUTER_API_KEY (process env only)."""
import os, json, time, hashlib, threading, urllib.request, urllib.error
ENDPOINTS = {'xai': ('https://api.x.ai/v1/chat/completions', 'XAI_API_KEY'),
             'openrouter': ('https://openrouter.ai/api/v1/chat/completions', 'OPENROUTER_API_KEY')}
OR_KEY_FILE = os.path.expanduser(os.environ.get('OPENROUTER_API_KEY_FILE', '~/.config/openrouter/api_key'))  # path only; the key itself is never stored in the repo
def load_openrouter_key():
    if not os.environ.get('OPENROUTER_API_KEY') and os.path.exists(OR_KEY_FILE):
        os.environ['OPENROUTER_API_KEY'] = open(OR_KEY_FILE).read().strip()
    return bool(os.environ.get('OPENROUTER_API_KEY'))
def available(backend='xai'):
    if backend == 'openrouter': return load_openrouter_key()
    return bool(os.environ.get(ENDPOINTS[backend][1]))
class RateLimited(Exception): pass
def chat_full(messages, model, backend='xai', temperature=0, max_tokens=2000, json_mode=False, retries=6, timeout=180):
    """Returns the full response JSON. Retries 429/5xx/timeouts with exponential backoff (honors Retry-After)."""
    url, env = ENDPOINTS[backend]
    body = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    if json_mode: body['response_format'] = {'type': 'json_object'}
    if backend == 'openrouter': body['usage'] = {'include': True}
    hdr = {'Authorization': 'Bearer ' + os.environ[env], 'Content-Type': 'application/json'}
    if backend == 'openrouter': hdr.update({'HTTP-Referer': 'https://localhost/margin', 'X-Title': 'Margin MLR eval judge'})
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=hdr)
            r = json.load(urllib.request.urlopen(req, timeout=timeout))
            if 'error' in r: raise RuntimeError(str(r['error'])[:300])
            return r
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504, 408):
                ra = e.headers.get('Retry-After'); wait = float(ra) if ra and ra.replace('.', '').isdigit() else min(60, 2 ** a * 2)
                time.sleep(wait); continue
            raise
        except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
            last = e; time.sleep(min(60, 2 ** a * 2))
    if isinstance(last, urllib.error.HTTPError) and last.code == 429: raise RateLimited(f'429 after {retries} tries')
    raise last
def chat(messages, model, temperature=0, max_tokens=2000, json_mode=False, retries=4, backend='xai'):
    r = chat_full(messages, model, backend, temperature, max_tokens, json_mode, retries)
    return r['choices'][0]['message']['content']
class Cache:
    """Append-only JSONL cache keyed by sha256(model + messages + params). Stores responses only (no keys)."""
    def __init__(self, path):
        self.path, self.lock, self.d = path, threading.Lock(), {}
        if os.path.exists(path):
            for l in open(path):
                try: x = json.loads(l); self.d[x['k']] = x['v']
                except Exception: pass
    @staticmethod
    def key(model, messages, **kw): return hashlib.sha256(json.dumps([model, messages, kw], sort_keys=True).encode()).hexdigest()
    def get(self, k): return self.d.get(k)
    def put(self, k, v):
        with self.lock:
            self.d[k] = v
            with open(self.path, 'a') as f: f.write(json.dumps({'k': k, 'v': v}, ensure_ascii=False) + '\n')
