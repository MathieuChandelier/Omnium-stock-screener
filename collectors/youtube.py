# -*- coding: utf-8 -*-
"""
collectors/youtube.py — refonte 2026-08-21

Collecteur d'interviews de dirigeants (CEO/CFO) et de contenus video
materiels, specifiques au titre.

POURQUOI LA REFONTE (deux defauts constates) :
  1. Doublons : la meme interview reprise par plusieurs chaines (ex. la
     version "Bloomberg Television" et la version "Bloomberg Podcasts" du
     meme entretien) generait plusieurs notifications pour UN evenement.
     -> dedup PAR EVENEMENT (fenetre de dates + similarite de titres),
        avec corroborations.
  2. Interviews manquees : l'ancienne requete unique
     '"<company>" CEO PDG interview' order=date etait trop etroite - le
     titre d'une interview ne contient souvent NI "CEO" NI "interview" ni
     meme la raison sociale complete, mais le NOM du dirigeant
     (ex. "Vlad Tenev's Vision for the Future of Robinhood").
     -> requetes multiples par ticker, centrees sur le NOM du dirigeant
        (source : data/executives.json), en order=date ET order=relevance.

STRATEGIE DE REQUETES (par ticker, fenetre publishedAfter = 7 jours) :
  (a) '"<company court>" interview'
  (b) '"<nom dirigeant>"'                (pour le CEO et chaque 'others')
  (c) '"<nom dirigeant>" "<company court>"'
  chacune en order=date ET order=relevance.
  Test de reference (2026-08-20, ROBINHOOD / Vlad Tenev) : les deux
  interviews CNBC et Bloomberg du jour ne remontent QUE via (b)/(c) ;
  l'ancienne requete ne retournait rien de recent.

CRITERES DE RETENTION (garder uniquement le critique) :
  - interview d'un dirigeant : son nom apparait dans titre/description ;
  - OU contenu materiel specifique au titre : nom de la societe + mot-cle
    materiel (acquisition, guidance, FDA, resignation, investor day...) ;
  - bruit ecarte : chaines de stock-picking generiques ("should you buy",
    "price prediction", "top N stocks"...), shorts/extraits < 2 min hors
    chaine officielle, resumes d'earnings sans dirigeant.

QUOTA API : search.list coute 100 unites ; jusqu'a 8 requetes/ticker sur
~59 tickers depasse le quota par defaut (10 000 unites/jour). Le script
bascule automatiquement sur le backend scraping (ytInitialData) pour les
tickers restants en cas de quotaExceeded — ou pour tout le run si
YOUTUBE_API_KEY est absente. Demander une hausse de quota ou etaler le
run si l'API devient la voie principale.

Usage :
  python collectors/youtube.py               # tout le manifest
  python collectors/youtube.py ROBINHOOD ... # sous-ensemble (debug/test)
  python collectors/youtube.py --scrape ...  # forcer le backend scraping
Env : YOUTUBE_API_KEY (optionnelle depuis la refonte, cf. QUOTA).
Ecrit artifacts/youtube.json au schema newsFeed :
  {"id":"TICKER-YYYYMMDD-slug","ticker","date","kind":"video","title",
   "summary","source","url","critical":true,"corroborations":[...]}
"""

import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import importlib.util as _ilu


def _load_state_module():
    """Charge lib/state.py par chemin absolu (voir historique : import
    par paquet echouait sur le runner GitHub Actions)."""
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib", "state.py")
    spec = _ilu.spec_from_file_location("omnium_news_state", state_path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_state = _load_state_module()
load_manifest = _state.load_manifest
load_ticker_json = _state.load_ticker_json
load_existing_news = _state.load_existing_news
write_artifact = _state.write_artifact

WINDOW_DAYS = 7
MAX_RESULTS_PER_QUERY = 10
EXECUTIVES_PATH = "data/executives.json"

# Suffixes juridiques/generiques a retirer pour obtenir le nom "court"
# reellement employe dans les titres de videos ("Robinhood Markets" ->
# "Robinhood", "Spotify Technology S.A." -> "Spotify").
_LEGAL_SUFFIXES = re.compile(
    r"\s+(inc\.?|corp\.?|corporation|company|co\.?|group|holdings?|markets|platforms|"
    r"technolog(?:y|ies)|s\.?a\.?|n\.?v\.?|s\.?e\.?|spa|plc|ag|sa|se|nv|\(pref\.?\))\s*$",
    re.I,
)

# Bruit typique des chaines de stock-picking / recyclage.
_NOISE_PATTERNS = re.compile(
    r"should you buy|buy or sell|price (?:prediction|target)|stock analysis|"
    r"top \d+ (?:stocks|actions)|stocks? to buy|technical analysis|"
    r"buy now|undervalued|analyse technique|faut-il acheter|objectif de cours|"
    r"live trading|day ?trading|millionaire|passive income|dividend portfolio|"
    r"\bexplained\b|\breaction\b|my take|what it means|top \d+ rules|"
    r"take the quiz|documentary|biography|life story",
    re.I,
)

# Mots-cles de materialite pour le contenu non-interview.
_MATERIAL_PATTERNS = re.compile(
    r"acquisition|acquires?|merger|takeover|divest|spin-?off|lawsuit|antitrust|"
    r"fda|recall|guidance|profit warning|resign|steps? down|appoint|successor|"
    r"investor day|capital markets day|keynote|product (?:launch|event)|"
    r"earnings call|conference call|rachat|fusion|proces|demission|nomination",
    re.I,
)

# Signaux qu'un dirigeant s'exprime LUI-MEME (interview, keynote, plateau)
# - par opposition aux videos de commentaire SUR le dirigeant, tres
# nombreuses pour les CEO de mega-caps (constate sur NVIDIA/Jensen Huang).
_INTERVIEW_PATTERNS = re.compile(
    r"\binterview|keynote|fireside|in conversation|sits? down|joins|"
    r"speaks? (?:with|to|at|about|on)|talks?\b|\bsays\b|\btells\b|discusses|"
    r"\bq&a\b|town hall|earnings call|conference call|full speech|testifies|"
    r"entretien|grand t[ée]moin|s'exprime|au micro",
    re.I,
)

# Chaines de reference (medias financiers, podcasts business de premier
# plan, organisateurs de conferences) : une video d'interview y est fiable
# meme sans mot-cle explicite dans le titre.
_TRUSTED_CHANNELS = re.compile(
    r"bloomberg|cnbc|cnn|fox business|yahoo finance|reuters|wall street journal|"
    r"wsj|financial times|forbes|the economist|axios|fortune|barron|"
    r"\bted\b|tedx|all-?in podcast|lex fridman|david rubenstein|sequoia|"
    r"20vc|bg2|acquired|big technology|milken|world economic forum|"
    r"goldman sachs|morgan stanley|j\.?p\.? ?morgan|stanford|harvard|mit\b|"
    r"bfm business|les echos|boursorama|zonebourse|euronext|b ?smart|"
    r"squawk|mad money|halftime report|norges bank",
    re.I,
)

# Mots vides pour la similarite de titres (dedup par evenement).
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "will", "your",
    "les", "des", "sur", "pour", "avec", "dans", "une", "est",
    "ceo", "cfo", "chief", "executive", "officer", "president", "chairman",
    "interview", "interviews", "talks", "talk", "says", "said", "discusses",
    "exclusive", "full", "video", "watch", "live", "podcast", "podcasts",
    "bloomberg", "cnbc", "reuters", "yahoo", "fox",
}


# ---------------------------------------------------------------------------
# Utilitaires texte
# ---------------------------------------------------------------------------

def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _ascii(s).lower()).strip()


def short_company_name(name: str) -> str:
    short = name or ""
    while True:
        stripped = _LEGAL_SUFFIXES.sub("", short).strip().rstrip(",")
        if stripped == short or not stripped:
            break
        short = stripped
    return short or name


def significant_tokens(title: str, exclude: set) -> set:
    toks = re.findall(r"[a-z0-9]{3,}", _norm(title))
    return {t for t in toks if t not in _STOPWORDS and t not in exclude}


def slugify(title: str, max_words: int = 4) -> str:
    words = re.findall(r"[a-z0-9]+", _norm(title))
    words = [w for w in words if w not in _STOPWORDS][:max_words] or words[:max_words]
    return "-".join(words) or "video"


def parse_duration_seconds(text_or_iso: str) -> int:
    """Accepte '14:07' / '1:20:04' (scrape) ou 'PT14M7S' (API)."""
    if not text_or_iso:
        return 0
    if text_or_iso.startswith("PT") or text_or_iso.startswith("P"):
        m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text_or_iso)
        if not m:
            return 0
        d, h, mn, s = (int(x or 0) for x in m.groups())
        return d * 86400 + h * 3600 + mn * 60 + s
    parts = [p for p in text_or_iso.strip().split(":") if p != ""]
    try:
        secs = 0
        for p in parts:
            secs = secs * 60 + int(p)
        return secs
    except ValueError:
        return 0


def parse_relative_date(text: str, now: datetime) -> str:
    """'17 hours ago' / 'Streamed 2 days ago' -> date ISO approximative."""
    m = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", text or "", re.I)
    if not m:
        return ""
    n, unit = int(m.group(1)), m.group(2).lower()
    delta = {
        "second": timedelta(seconds=n), "minute": timedelta(minutes=n),
        "hour": timedelta(hours=n), "day": timedelta(days=n),
        "week": timedelta(weeks=n), "month": timedelta(days=30 * n),
        "year": timedelta(days=365 * n),
    }[unit]
    return (now - delta).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Backends de recherche : API YouTube Data v3, et scraping ytInitialData
# ---------------------------------------------------------------------------

class QuotaExceeded(Exception):
    pass


def _http_get(url: str) -> str:
    """urllib avec repli curl (certains postes locaux n'ont pas la chaine
    de certificats pour urllib ; curl utilise les certs systeme)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except Exception:
        out = subprocess.run(
            ["curl", "-s", "-m", "25",
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
             "-H", "Accept-Language: en-US,en;q=0.9",
             "-H", "Cookie: CONSENT=YES+1",
             url],
            capture_output=True, text=True, timeout=40,
        )
        return out.stdout


def api_search(api_key: str, query: str, order: str, published_after: str) -> list:
    params = urllib.parse.urlencode({
        "part": "snippet", "q": query, "type": "video", "order": order,
        "publishedAfter": published_after, "maxResults": MAX_RESULTS_PER_QUERY,
        "key": api_key,
    })
    raw = _http_get(f"https://www.googleapis.com/youtube/v3/search?{params}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if "error" in data:
        reasons = [e.get("reason", "") for e in data["error"].get("errors", [])]
        if "quotaExceeded" in reasons or data["error"].get("code") == 403:
            raise QuotaExceeded(str(reasons))
        print(f"  [ERREUR API] {data['error'].get('message','?')}", file=sys.stderr)
        return []
    out = []
    for entry in data.get("items", []):
        vid = entry.get("id", {}).get("videoId")
        if not vid:
            continue
        sn = entry.get("snippet", {})
        out.append({
            "videoId": vid,
            "title": sn.get("title", "").strip(),
            "channel": sn.get("channelTitle", "").strip(),
            "description": sn.get("description", "").strip(),
            "date": (sn.get("publishedAt", "") or "")[:10],
            "durationSeconds": 0,  # complete via api_video_details
        })
    return out


def api_video_details(api_key: str, video_ids: list) -> dict:
    """durations + descriptions completes, 1 unite / 50 ids."""
    details = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        params = urllib.parse.urlencode({
            "part": "contentDetails,snippet", "id": ",".join(chunk), "key": api_key,
        })
        try:
            data = json.loads(_http_get(f"https://www.googleapis.com/youtube/v3/videos?{params}"))
        except json.JSONDecodeError:
            continue
        for it in data.get("items", []):
            details[it.get("id")] = {
                "durationSeconds": parse_duration_seconds(
                    it.get("contentDetails", {}).get("duration", "")),
                "description": it.get("snippet", {}).get("description", ""),
            }
    return details


# sp= de YouTube web : tri par date / filtre "cette semaine" (relevance).
_SP_ORDER_DATE = "CAI%3D"
_SP_THIS_WEEK = "EgIIAw%3D%3D"


def scrape_search(query: str, order: str, now: datetime) -> list:
    sp = _SP_ORDER_DATE if order == "date" else _SP_THIS_WEEK
    url = ("https://www.youtube.com/results?search_query="
           + urllib.parse.quote(query) + "&sp=" + sp)
    html = _http_get(url)
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out = []

    def walk(o):
        if isinstance(o, dict):
            if "videoRenderer" in o:
                v = o["videoRenderer"]
                title = "".join(r.get("text", "") for r in v.get("title", {}).get("runs", []))
                channel = "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", []))
                pub = v.get("publishedTimeText", {}).get("simpleText", "")
                desc = ""
                for snip in v.get("detailedMetadataSnippets", []) or []:
                    desc += "".join(r.get("text", "") for r in
                                    snip.get("snippetText", {}).get("runs", []))
                out.append({
                    "videoId": v.get("videoId"),
                    "title": title.strip(),
                    "channel": channel.strip(),
                    "description": desc.strip(),
                    "date": parse_relative_date(pub, now),
                    "durationSeconds": parse_duration_seconds(
                        v.get("lengthText", {}).get("simpleText", "")),
                })
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(data)
    return [v for v in out if v["videoId"]]


# ---------------------------------------------------------------------------
# Collecte par ticker
# ---------------------------------------------------------------------------

def build_queries(company_short: str, exec_names: list) -> list:
    """(requete, order) — (a)/(b)/(c) x (date, relevance), dedupliquees."""
    queries = [f'"{company_short}" interview']
    for name in exec_names:
        queries.append(f'"{name}"')
        queries.append(f'"{name}" "{company_short}"')
    seen, out = set(), []
    for q in queries:
        for order in ("date", "relevance"):
            key = (q.lower(), order)
            if key not in seen:
                seen.add(key)
                out.append((q, order))
    return out


_CAPS_WHITELIST = {"CEO", "CFO", "COO", "CTO", "IPO", "FDA", "SEC", "ETF",
                   "USA", "GDP", "EPS", "TED", "LVMH", "BNP", "UCB", "IBKR",
                   "AVGO", "CPRT", "ABNB", "SNAP", "META", "SFM", "ABT", "AAPL"}


def _looks_clickbait(title: str) -> bool:
    """>= 2 mots entierement en capitales (hors sigles usuels) = titre
    racoleur de chaine de recyclage ('BOLD Move', 'Goes to WAR')."""
    caps = [w for w in re.findall(r"\b[A-Z]{3,}\b", title or "")
            if w not in _CAPS_WHITELIST]
    return len(caps) >= 2


def is_critical(video: dict, company_aliases: list, exec_names: list) -> str:
    """Retourne 'exec' / 'material' si la video est a garder, '' sinon."""
    text = _norm(video["title"] + " " + video.get("description", ""))
    channel = _norm(video.get("channel", ""))

    if _NOISE_PATTERNS.search(text) or _NOISE_PATTERNS.search(channel):
        return ""
    if _looks_clickbait(video["title"]):
        return ""

    company_present = any(_norm(a) in text or _norm(a) in channel for a in company_aliases)
    # Chaine OFFICIELLE = egalite stricte avec un alias societe ("Robinhood",
    # "NVIDIA") - un simple `in` laisserait passer les chaines de fans/spam
    # nommees "Nvidia Media", "Nvidia News", etc. (constate sur NVIDIA).
    official = any(channel == _norm(a) or channel == _norm(a) + " official"
                   for a in company_aliases)
    trusted = bool(_TRUSTED_CHANNELS.search(channel))

    exec_present = False
    for name in exec_names:
        n = _norm(name)
        if n and n in text:
            exec_present = True
            break
        # nom de famille seul, mais uniquement en contexte societe
        last = n.split()[-1] if n else ""
        if len(last) >= 4 and last in text and company_present:
            exec_present = True
            break

    # shorts / extraits recycles : < 2 min hors chaine officielle
    dur = video.get("durationSeconds", 0)
    if 0 < dur < 120 and not official:
        return ""

    # Dirigeant qui S'EXPRIME (interview/keynote/plateau) - il faut soit un
    # signal explicite d'interview, soit une chaine de reference/officielle,
    # sinon c'est du commentaire SUR le dirigeant (bruit majoritaire).
    if exec_present and (official or trusted or _INTERVIEW_PATTERNS.search(text)):
        return "exec"
    # Contenu materiel specifique au titre, hors interview : uniquement
    # depuis une chaine de reference ou officielle (les communiques bruts
    # sont deja couverts par le collecteur communiques).
    if company_present and _MATERIAL_PATTERNS.search(text) and (official or trusted):
        return "material"
    return ""


def group_events(videos: list, company_aliases: list, exec_names: list) -> list:
    """Dedup par evenement : meme ticker (implicite), dates proches,
    similarite des tokens significatifs du titre. Retourne des groupes
    [principal, corroboration, ...] tries qualite decroissante."""
    # N'exclure de la similarite que le nom COURT de la societe et les noms
    # de dirigeants : exclure la raison sociale complete supprimerait des
    # mots porteurs de sens ("Robinhood Markets" -> 'markets' doit compter
    # pour rapprocher deux titres sur les prediction markets).
    shortest_alias = min(company_aliases, key=len) if company_aliases else ""
    exclude = set()
    for a in [shortest_alias] + exec_names:
        exclude |= set(re.findall(r"[a-z0-9]{3,}", _norm(a)))

    def quality(v):
        official = any(_norm(a) in _norm(v.get("channel", "")) for a in company_aliases + exec_names)
        return (1 if official else 0, v.get("durationSeconds", 0))

    groups = []
    for v in sorted(videos, key=quality, reverse=True):
        v_toks = significant_tokens(v["title"], exclude)
        v_date = v.get("date", "")
        placed = False
        for g in groups:
            p = g[0]
            try:
                d1 = datetime.strptime(v_date, "%Y-%m-%d")
                d2 = datetime.strptime(p.get("date", ""), "%Y-%m-%d")
                close = abs((d1 - d2).days) <= 3
            except ValueError:
                close = True  # date approximative/absente : ne bloque pas
            if not close:
                continue
            p_toks = significant_tokens(p["title"], exclude)
            if v_toks and p_toks:
                shared = v_toks & p_toks
                sim = len(shared) / min(len(v_toks), len(p_toks))
                same = sim >= 0.6 and len(shared) >= 2
            else:
                # trop peu de signal : ne fusionne que si meme "maison"
                same = _norm(v.get("channel", "")).split(" ")[0] == \
                       _norm(p.get("channel", "")).split(" ")[0] and bool(v_toks) == bool(p_toks)
            if same:
                g.append(v)
                placed = True
                break
        if not placed:
            groups.append([v])
    return groups


def make_summary(principal: dict, reason: str, ceo: str, company: str) -> str:
    if reason == "exec":
        base = f"Interview/prise de parole d'un dirigeant de {company}"
        if ceo and _norm(ceo) in _norm(principal["title"] + " " + principal.get("description", "")):
            base = f"Interview de {ceo} ({company})"
    else:
        base = f"Contenu materiel specifique a {company}"
    base += f" — {principal.get('channel', 'YouTube')}"
    desc = (principal.get("description") or "").strip().split("\n")[0]
    if desc:
        base += f". {desc[:180]}"
    return base


def collect_for_ticker(ticker: str, backend: str, api_key: str,
                       window_start: datetime, now: datetime,
                       existing_urls: set, executives: dict) -> tuple:
    tdata = load_ticker_json(ticker) or {}
    company = tdata.get("name", ticker)
    company_short = short_company_name(company)
    company_aliases = list({company, company_short})

    exec_entry = executives.get(ticker, {}) or {}
    ceo = (exec_entry.get("ceo") or "").strip()
    exec_names = [n for n in [ceo] + list(exec_entry.get("others", [])) if n]

    published_after = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    window_start_date = window_start.strftime("%Y-%m-%d")

    seen_ids, candidates = set(), []
    used_backend = backend
    for query, order in build_queries(company_short, exec_names):
        try:
            if used_backend == "api":
                results = api_search(api_key, query, order, published_after)
            else:
                results = scrape_search(query, order, now)
        except QuotaExceeded:
            print(f"  [QUOTA] bascule scraping a partir de {ticker}", file=sys.stderr)
            used_backend = "scrape"
            results = scrape_search(query, order, now)
        except Exception as e:
            print(f"  [ERREUR] {ticker} '{query}' ({order}): {e}", file=sys.stderr)
            continue
        for v in results:
            if v["videoId"] in seen_ids:
                continue
            seen_ids.add(v["videoId"])
            # fraicheur : le backend scrape ne filtre pas nativement
            if v.get("date") and v["date"] < window_start_date:
                continue
            if f"https://www.youtube.com/watch?v={v['videoId']}" in existing_urls:
                continue
            candidates.append(v)

    # durations/descriptions completes si l'API est disponible
    if used_backend == "api" and candidates:
        try:
            details = api_video_details(api_key, [v["videoId"] for v in candidates])
            for v in candidates:
                d = details.get(v["videoId"])
                if d:
                    v["durationSeconds"] = d["durationSeconds"] or v["durationSeconds"]
                    v["description"] = d["description"] or v["description"]
        except Exception:
            pass

    retained = []
    for v in candidates:
        reason = is_critical(v, company_aliases, exec_names)
        if reason:
            v["_reason"] = reason
            retained.append(v)

    items = []
    for group in group_events(retained, company_aliases, exec_names):
        principal = group[0]
        date = principal.get("date") or now.strftime("%Y-%m-%d")
        items.append({
            "id": f"{ticker}-{date.replace('-', '')}-{slugify(principal['title'])}",
            "ticker": ticker,
            "date": date,
            "kind": "video",
            "title": principal["title"],
            "summary": make_summary(principal, principal.get("_reason", "exec"), ceo, company_short),
            "source": principal.get("channel", "YouTube"),
            "url": f"https://www.youtube.com/watch?v={principal['videoId']}",
            "critical": True,
            "corroborations": [
                {
                    "title": c["title"],
                    "source": c.get("channel", "YouTube"),
                    "url": f"https://www.youtube.com/watch?v={c['videoId']}",
                    "date": c.get("date", ""),
                }
                for c in group[1:]
            ],
        })
    return items, used_backend


# ---------------------------------------------------------------------------

def load_executives(path=EXECUTIVES_PATH) -> dict:
    if not os.path.exists(path):
        print(f"[AVERTISSEMENT] {path} absent - requetes CEO desactivees", file=sys.stderr)
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def main(argv):
    args = [a for a in argv if not a.startswith("-")]
    force_scrape = "--scrape" in argv

    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    backend = "scrape" if (force_scrape or not api_key) else "api"
    if backend == "scrape" and not force_scrape:
        print("[INFO] YOUTUBE_API_KEY absente - backend scraping (ytInitialData)", file=sys.stderr)

    manifest = load_manifest()
    tickers = [t for t in args if t in manifest] or manifest
    executives = load_executives()
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=WINDOW_DAYS)

    all_items, error_count = [], 0
    for ticker in tickers:
        existing_urls = {it.get("url", "") for it in load_existing_news(ticker)}
        try:
            items, backend = collect_for_ticker(
                ticker, backend, api_key, window_start, now, existing_urls, executives)
        except Exception as e:
            print(f"  [ERREUR] {ticker}: {e}", file=sys.stderr)
            error_count += 1
            continue
        if items:
            print(f"  [{ticker}] {len(items)} evenement(s) "
                  f"({sum(len(i['corroborations']) for i in items)} corroboration(s))")
        all_items.extend(items)

    write_artifact("youtube", all_items)
    print(f"[youtube] {len(all_items)} evenements, {error_count} tickers en erreur "
          f"sur {len(tickers)} (backend final : {backend})")
    if tickers and error_count >= len(tickers) * 0.8:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
