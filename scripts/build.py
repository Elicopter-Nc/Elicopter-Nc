"""Génère les SVG du README de profil, dans le style du portfolio « Le bureau d'Eli ».

GitHub n'exécute ni CSS ni JS dans un README, mais il affiche des SVG : chaque bloc du README
est dessiné en SVG, avec les polices du portfolio intégrées (sous-ensembles woff2) et des
animations CSS internes au SVG. Les chiffres (stars, commits, repos, contributions, langages,
derniers commits) viennent de l'API GitHub et sont rafraîchis par .github/workflows/refresh.yml.

Usage : GITHUB_TOKEN=... python scripts/build.py
"""
import base64, html, io, json, os, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONTS_DIR = ROOT / "scripts" / "fonts"
USER = "Elicopter-Nc"
TZ = ZoneInfo("Pacific/Noumea")

# ---------------------------------------------------------------- polices
FONTS = {  # clé -> (famille CSS, graisse, fichier)
    "display": ("EliDisplay", 800, "unbounded-800.ttf"),
    "body": ("EliBody", 400, "instr-400.ttf"),
    "bodyb": ("EliBody", 600, "instr-600.ttf"),
    "mono": ("EliMono", 500, "jb-500.ttf"),
    "monob": ("EliMono", 700, "jb-700.ttf"),
    "hand": ("EliHand", 700, "caveat-700.ttf"),
}
_tt = {}


def font(key):
    if key not in _tt:
        t = TTFont(FONTS_DIR / FONTS[key][2])
        _tt[key] = (t.getBestCmap(), t["hmtx"].metrics, t["head"].unitsPerEm)
    return _tt[key]


def measure(text, key, size, spacing=0):
    cmap, hmtx, upm = font(key)
    w = 0
    for ch in text:
        g = cmap.get(ord(ch))
        w += (hmtx[g][0] if g else upm * 0.5) / upm * size + spacing
    return w


def wrap(text, key, size, maxw):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, key, size) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def ellipsize(text, key, size, maxw):
    if measure(text, key, size) <= maxw:
        return text
    while text and measure(text + "…", key, size) > maxw:
        text = text[:-1]
    return text.rstrip() + "…"


def esc(s):
    return html.escape(s, quote=True)


class Svg:
    """Petit constructeur de SVG qui retient les caractères utilisés par police, pour les sous-ensembles."""

    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.vx = 0  # origine x du viewBox (pour découper une scène en morceaux)
        self.parts, self.defs, self.css = [], [], []
        self.used = {}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, key, size, fill, anchor="start", extra=""):
        self.used.setdefault(key, set()).update(s)
        fam, wt, _ = FONTS[key]
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-weight="{wt}" font-size="{size}" fill="{fill}"{a} {extra}>{esc(s)}</text>')

    def font_css(self):
        out = []
        for key, chars in self.used.items():
            fam, wt, fname = FONTS[key]
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga"]
            sub = subset.Subsetter(opts)
            f = TTFont(FONTS_DIR / fname)
            sub.populate(text="".join(chars) + " ")
            sub.subset(f)
            buf = io.BytesIO()
            f.flavor = "woff2"
            f.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            out.append(f"@font-face{{font-family:{fam};font-weight:{wt};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
        return "".join(out)

    def save(self, name):
        css = self.font_css() + "".join(self.css)
        # Les animations s'arrêtent pour qui préfère réduire les mouvements.
        css += "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{self.vx} 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" role="img">'
               f"<title>{esc(self.title)}</title><style>{css}</style><defs>{''.join(self.defs)}</defs>{''.join(self.parts)}</svg>")
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"{name}: {len(svg) // 1024} Ko")


# ---------------------------------------------------------------- défs communes
SHADOW = ('<filter id="sh" x="-30%" y="-30%" width="160%" height="160%">'
          '<feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#000" flood-opacity=".3"/></filter>'
          '<filter id="shs" x="-30%" y="-30%" width="160%" height="160%">'
          '<feDropShadow dx="0" dy="3" stdDeviation="2.5" flood-color="#000" flood-opacity=".3"/></filter>')


def wood(s, radius=18):
    """Le plateau en bois du bureau : dégradé, veinure et vignette, comme .room dans le CSS du portfolio."""
    s.defs.append(
        '<linearGradient id="wood" x1="0" x2="1"><stop offset="0" stop-color="#b58a5e"/><stop offset=".5" stop-color="#a77c51"/><stop offset="1" stop-color="#b58a5e"/></linearGradient>'
        '<pattern id="grain" width="23" height="10" patternUnits="userSpaceOnUse"><rect width="1" height="10" fill="rgba(70,40,15,.10)"/><rect x="7" width="1" height="10" fill="rgba(70,40,15,.10)"/></pattern>'
        '<radialGradient id="vig" cx=".5" cy=".45" r=".75"><stop offset=".55" stop-color="#28140a" stop-opacity="0"/><stop offset="1" stop-color="#28140a" stop-opacity=".22"/></radialGradient>'
        f'<clipPath id="frame"><rect width="{s.w}" height="{s.h}" rx="{radius}"/></clipPath>' + SHADOW)
    s.add(f'<g clip-path="url(#frame)"><rect width="{s.w}" height="{s.h}" fill="url(#wood)"/>'
          f'<rect width="{s.w}" height="{s.h}" fill="url(#grain)"/><rect width="{s.w}" height="{s.h}" fill="url(#vig)"/>')


def label(s, x, y, small, big, w, rot=-1.5):
    """Étiquette papier, comme celle du dossier Projets du portfolio."""
    s.add(f'<g transform="translate({x} {y}) rotate({rot})" filter="url(#shs)"><rect width="{w}" height="60" rx="3" fill="#fbfaf6"/>')
    s.text(18, 20, small, "mono", 11, "#6b6e72", extra='letter-spacing="1"')
    s.text(18, 50, big, "display", 26, "#1d1f22", extra='letter-spacing="-.8"')
    s.add("</g>")


# ---------------------------------------------------------------- données GitHub
REPOS = ["kairos", "Focus"]  # repli si aucun repo n'est épinglé sur le profil
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def get(url, token=None, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-build", "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read() if raw else json.load(r)


def iso_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ)


def github_data():
    token = os.environ.get("GITHUB_TOKEN")
    user = get(f"https://api.github.com/users/{USER}", token)
    repos = get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", token)
    d = {
        "avatar": base64.b64encode(get(user["avatar_url"] + "&s=240", raw=True)).decode(),
        "joined": iso_dt(user["created_at"]),
        "followers": user["followers"],
        "repos": user["public_repos"],
        "stars": sum(r["stargazers_count"] for r in repos if not r["fork"]),
        "commits": None,
        "calendar": None,
        "pinned_order": REPOS,
        "pinned": {},
    }
    if token:  # l'API GraphQL demande un jeton (le GITHUB_TOKEN du workflow suffit)
        q = {"query": "query($l:String!){user(login:$l){"
                      "contributionsCollection{totalCommitContributions restrictedContributionsCount "
                      "contributionCalendar{totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}} "
                      "pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{name}}}}}",
             "variables": {"l": USER}}
        req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps(q).encode(),
                                     headers={"Authorization": f"Bearer {token}", "User-Agent": "profile-readme-build"})
        with urllib.request.urlopen(req, timeout=20) as r:
            gq = json.load(r)["data"]["user"]
        cc = gq["contributionsCollection"]
        d["commits"] = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
        d["calendar"] = cc["contributionCalendar"]
        d["pinned_order"] = [n["name"] for n in gq["pinnedItems"]["nodes"]] or REPOS
    for name in d["pinned_order"]:
        r = get(f"https://api.github.com/repos/{USER}/{name}", token)
        d["pinned"][name] = {"name": r["name"], "desc": r["description"] or "", "stars": r["stargazers_count"], "forks": r["forks_count"],
                             "pushed": iso_dt(r["pushed_at"]), "private": r["private"],
                             "langs": get(f"https://api.github.com/repos/{USER}/{name}/languages", token)}
    # langages cumulés sur tous mes repos publics (hors forks et hors ce repo de profil)
    mine = [r for r in repos if not r["fork"] and not r["private"] and r["name"] != USER]
    total = {}
    for r in mine:
        for lang, n in get(f"https://api.github.com/repos/{USER}/{r['name']}/languages", token).items():
            total[lang] = total.get(lang, 0) + n
    d["languages"] = sorted(total.items(), key=lambda x: -x[1])
    # activité récente : derniers commits sur les repos poussés le plus récemment, repo de profil compris.
    # Les commits automatiques du workflow sont écartés par le filtre author= (leur auteur est github-actions[bot]).
    publics = [r for r in repos if not r["fork"] and not r["private"]]
    acts = []
    for r in sorted(publics, key=lambda r: r["pushed_at"], reverse=True)[:6]:
        try:
            for c in get(f"https://api.github.com/repos/{USER}/{r['name']}/commits?author={USER}&per_page=4", token):
                acts.append({"repo": r["name"], "msg": c["commit"]["message"].splitlines()[0], "date": iso_dt(c["commit"]["author"]["date"])})
        except Exception as e:  # repo vide, etc.
            print("commits indisponibles pour", r["name"], e)
    d["activity"] = sorted(acts, key=lambda a: a["date"], reverse=True)[:4]
    return d


# ---------------------------------------------------------------- 1. la carte « passeport » posée sur le bureau
KEYROWS = [
    [("²", 1), ("&", 1), ("é", 1), ('"', 1), ("'", 1), ("(", 1), ("-", 1), ("è", 1), ("_", 1), ("ç", 1), ("à", 1), (")", 1), ("=", 1), ("⌫", 1.7)],
    [("⇥", 1.5), ("A", 1), ("Z", 1), ("E", 1), ("R", 1), ("T", 1), ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1), ("^", 1), ("$", 1), ("↵", 1.2)],
    [("⇪", 1.8), ("Q", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1), ("H", 1), ("J", 1), ("K", 1), ("L", 1), ("M", 1), ("ù", 1), ("*", 1)],
    [("⇧", 1.3), ("<", 1), ("W", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1), ("N", 1), (",", 1), (";", 1), (":", 1), ("!", 1), ("⇧", 2.2)],
    [("Ctrl", 1.5), ("≡", 1), ("Alt", 1.3), (" ", 6.2), ("AltGr", 1.5), ("Ctrl", 1.5)],
]
HL = {"E": 0, "L": 1, "I": 2}  # E-L-I tapé en boucle, comme à l'ouverture du portfolio


def keyboard(s, kx, ky, kw, kh):
    pad, gap = 11, 5
    s.add(f'<rect x="{kx}" y="{ky}" width="{kw}" height="{kh}" rx="14" fill="url(#kb)" filter="url(#sh)"/>')
    rh = (kh - 2 * pad - 4 * gap) / 5
    for r, row in enumerate(KEYROWS):
        unit = (kw - 2 * pad - gap * (len(row) - 1)) / sum(k for _, k in row)
        x, y = kx + pad, ky + pad + r * (rh + gap)
        for lab, k in row:
            w = unit * k
            hl = lab in HL and r in (1, 2)
            cls = f' class="k k{HL[lab]}"' if hl else ""
            base, top, ink = ("#c98407", "url(#keyhl)", "#3a2600") if hl else ("#b9b8b3", "url(#key)", "#3a3c40")
            s.add(f'<g{cls}><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{rh:.1f}" rx="5" fill="{base}"/>'
                  f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{rh - 3:.1f}" rx="5" fill="{top}"/>')
            if lab.strip():
                s.text(x + 5, y + 13, lab, "monob" if hl else "mono", 10.5, ink)
            s.add("</g>")
            x += w + gap


def passeport(d):
    s = Svg(1200, 610, "Eli · Full-stack dev, et mes derniers commits sur le téléphone")
    wood(s)
    s.css.append(
        "@keyframes press{0%,9%,100%{transform:none}3%{transform:translateY(2.5px)}}"
        ".k{animation:press 3.2s ease-out infinite}.k1{animation-delay:.28s}.k2{animation-delay:.56s}"
        "@keyframes sway{0%,100%{transform:none}50%{transform:rotate(4deg) scale(1.02)}}.leaf{animation:sway 5s ease-in-out infinite}"
        "@keyframes steam{0%{opacity:0;transform:translate(0,0) scale(.5)}25%{opacity:.7}100%{opacity:0;transform:translate(14px,-110px) scale(1.7)}}"
        ".st{animation:steam 4.2s ease-in-out infinite;opacity:0}.st2{animation-delay:1.4s}.st3{animation-delay:2.8s}"
        "@keyframes crema{to{transform:rotate(360deg)}}.crema{animation:crema 18s linear infinite}"
        "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}.caret{animation:blink 1.1s steps(1) infinite}")
    s.defs.append(
        '<linearGradient id="kb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b3f45"/><stop offset="1" stop-color="#2c2f34"/></linearGradient>'
        '<linearGradient id="key" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f2f1ee"/><stop offset="1" stop-color="#d9d8d4"/></linearGradient>'
        '<linearGradient id="keyhl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffcf5a"/><stop offset="1" stop-color="#f0a81c"/></linearGradient>'
        '<linearGradient id="mon" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a2d31"/><stop offset="1" stop-color="#141619"/></linearGradient>'
        '<linearGradient id="foot" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3d42"/><stop offset="1" stop-color="#26282c"/></linearGradient>'
        '<linearGradient id="mouse" x1="0" x2="1"><stop offset="0" stop-color="#e9e8e4"/><stop offset="1" stop-color="#cfcec9"/></linearGradient>'
        '<linearGradient id="leafg" x1="0" x2="1"><stop offset="0" stop-color="#2f6b3c"/><stop offset=".6" stop-color="#4f9a55"/><stop offset="1" stop-color="#6fb86c"/></linearGradient>'
        # radial-gradient(#5a3f2a 55%,#c9764a 57%,#b0613a 70%,#9a5330 72%) du portfolio, ramené au rayon du pot (×√2)
        '<radialGradient id="pot"><stop offset=".778" stop-color="#5a3f2a"/><stop offset=".806" stop-color="#c9764a"/><stop offset=".99" stop-color="#b0613a"/><stop offset="1" stop-color="#9a5330"/></radialGradient>'
        '<filter id="leafsh" x="-20%" y="-60%" width="140%" height="220%"><feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000" flood-opacity=".25"/></filter>'
        '<radialGradient id="cup"><stop offset=".5" stop-color="#3a2416"/><stop offset=".56" stop-color="#5b3a22"/><stop offset=".59" stop-color="#f4f1ea"/><stop offset=".95" stop-color="#e2ded5"/><stop offset="1" stop-color="#cfcac0"/></radialGradient>'
        '<radialGradient id="puff"><stop offset="0" stop-color="#fff" stop-opacity=".6"/><stop offset=".65" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="pen" x1="0" x2="1"><stop offset="0" stop-color="#1f3fa8"/><stop offset=".5" stop-color="#2f5ad6"/><stop offset="1" stop-color="#1a368f"/></linearGradient>'
        '<linearGradient id="scr" x1="0" y1="0" x2=".6" y2="1"><stop offset="0" stop-color="#2e372d"/><stop offset="1" stop-color="#1b2220"/></linearGradient>'
        '<clipPath id="av"><rect width="168" height="168" rx="10"/></clipPath>'
        '<filter id="blur"><feGaussianBlur stdDeviation="5"/></filter>')

    # écran, tapis, clavier, souris
    s.add('<rect x="790" y="-10" width="90" height="90" rx="18" fill="url(#foot)" filter="url(#sh)"/>'
          '<rect x="630" y="-14" width="420" height="44" rx="8" fill="url(#mon)" filter="url(#sh)"/>')
    s.add('<rect x="612" y="96" width="560" height="262" rx="24" fill="#2f3b38" stroke="#26302d" stroke-width="5" filter="url(#sh)"/>')
    keyboard(s, 636, 124, 440, 186)
    s.add('<g transform="translate(1094 150) rotate(4)" filter="url(#sh)"><rect width="52" height="86" rx="26" ry="32" fill="url(#mouse)"/>'
          '<rect x="25.3" y="0" width="1.5" height="36" fill="#a9a8a3"/><rect x="21" y="12" width="10" height="16" rx="5" fill="#77767a"/></g>')
    # plante du portfolio (buildPlant dans desk.js) : pot vu de dessus, 11 feuilles posées par-dessus,
    # chacune pivotant autour du centre comme .leaf (transform-origin:0 50%)
    S_, LW, LH = 220, 220 * .46, 220 * .16  # boîte de la plante, largeur et hauteur d'une feuille
    s.add('<g transform="translate(84 76)">')
    s.add(f'<circle r="{S_ * .28:.1f}" fill="url(#pot)" filter="url(#sh)"/>')
    leaf = f'M0 {-LH / 2:.1f}A{LW:.1f} {LH:.1f} 0 0 1 {LW:.1f} {LH / 2:.1f}A{LW:.1f} {LH:.1f} 0 0 1 0 {-LH / 2:.1f}Z'
    for i in range(11):
        rot, sc, dl = i * 33 + (i % 2) * 9, .8 + (i % 3) * .14, i * .45
        s.add(f'<g transform="rotate({rot}) scale({sc:.2f})"><g class="leaf" style="animation-delay:-{dl:.2f}s">'
              f'<path d="{leaf}" fill="url(#leafg)" filter="url(#leafsh)"/></g></g>')
    s.add('</g>')
    # stylo, tasse de café, petite voiture
    s.add('<g transform="translate(600 450) rotate(-62)" filter="url(#sh)"><rect width="12" height="120" rx="5" fill="url(#pen)"/>'
          '<path d="M2 120H10L6.6 142H5.4Z" fill="#a9a59d"/></g>')
    s.add('<g transform="translate(770 488)"><g filter="url(#sh)"><path d="M40-16A16 16 0 0 1 40 16" fill="none" stroke="#e2ded5" stroke-width="12"/>'
          '<circle r="56" fill="url(#cup)"/></g>'
          '<g class="crema"><path d="M-18-22A28 28 0 0 1 20-20" stroke="#d6a069" stroke-opacity=".35" stroke-width="5" fill="none" stroke-linecap="round"/>'
          '<path d="M16 22A28 28 0 0 1-20 18" stroke="#d6a069" stroke-opacity=".28" stroke-width="4" fill="none" stroke-linecap="round"/></g>'
          '<ellipse cx="-10" cy="-14" rx="8" ry="5" fill="#ffebc8" fill-opacity=".3"/>'
          '<g filter="url(#blur)"><circle class="st" r="28" fill="url(#puff)"/><circle class="st st2" cx="14" r="26" fill="url(#puff)"/><circle class="st st3" cx="-14" r="30" fill="url(#puff)"/></g></g>')
    s.add('<g transform="translate(900 440) rotate(28)" filter="url(#sh)"><rect x="-5" y="12" width="8" height="16" rx="3" fill="#1b1d20"/><rect x="39" y="12" width="8" height="16" rx="3" fill="#1b1d20"/>'
          '<rect x="-5" y="62" width="8" height="16" rx="3" fill="#1b1d20"/><rect x="39" y="62" width="8" height="16" rx="3" fill="#1b1d20"/>'
          '<rect width="42" height="92" rx="14" fill="#f08a24"/><rect x="6" y="20" width="30" height="14" rx="4" fill="#2a2d31"/>'
          '<rect x="7" y="38" width="28" height="26" rx="4" fill="#e07514"/><rect x="8" y="68" width="26" height="9" rx="3" fill="#2a2d31"/>'
          '<rect x="16" y="0" width="4" height="92" fill="#1b1d20"/><rect x="23" y="0" width="4" height="92" fill="#1b1d20"/>'
          '<rect x="5" y="2" width="8" height="4" rx="2" fill="#fff3c4"/><rect x="29" y="2" width="8" height="4" rx="2" fill="#fff3c4"/></g>')

    # la carte : avatar, nom, citation et stats (le « passeport » de l'ancien README)
    s.add('<g transform="translate(46 186) rotate(-2)" filter="url(#sh)"><rect width="540" height="330" rx="8" fill="#fdfcf9"/>')
    s.add(f'<g transform="translate(28 30)"><rect x="-6" y="-6" width="180" height="180" rx="14" fill="#e3e0d6"/>'
          f'<image href="data:image/png;base64,{d["avatar"]}" width="168" height="168" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/></g>')
    s.text(226, 84, "Eli", "display", 56, "#1b1d20", extra='letter-spacing="-1.5"')
    s.add(f'<rect class="caret" x="{238 + measure("Eli", "display", 56, -1.5):.0f}" y="40" width="5" height="46" fill="#f0a81c"/>')
    s.text(228, 122, "Full-stack dev", "body", 22, "#55595f")
    s.text(228, 162, "@Elicopter-Nc", "mono", 14, "#2b5fd9")
    s.add('<rect x="28" y="226" width="484" height="2" fill="#1b1d20"/>')
    m = MOIS[d["joined"].month - 1]
    joined = f"{m[:4].rstrip('.')}. {d['joined'].year}" if len(m) > 5 else f"{m} {d['joined'].year}"
    stats = [("MEMBRE DEPUIS", joined), ("STARS", str(d["stars"])),
             ("COMMITS · 1 AN", str(d["commits"]) if d["commits"] is not None else "—"), ("FOLLOWERS", str(d["followers"]))]
    cw = 484 / 4
    for i, (lab, val) in enumerate(stats):
        x = 28 + i * cw
        if i:
            s.add(f'<rect x="{x - 1:.0f}" y="244" width="1" height="62" fill="#e3e0d6"/>')
        s.text(x + (12 if i else 0), 264, lab, "mono", 9.5, "#6b6e72", extra='letter-spacing=".8"')
        s.text(x + (12 if i else 0), 300, val, "display", 22 if len(val) < 6 else 17, "#1b1d20", extra='letter-spacing="-.5"')
    s.add("</g>")

    # téléphone : activité récente
    s.add('<g transform="translate(1000 292) rotate(4)" filter="url(#sh)"><rect width="172" height="300" rx="26" fill="#111316"/>'
          '<rect x="9" y="9" width="154" height="282" rx="19" fill="url(#scr)"/><rect x="66" y="16" width="40" height="8" rx="4" fill="#111316"/>')
    s.text(24, 50, "Activité", "display", 15, "#e9efe2")
    s.text(24, 66, "DERNIERS COMMITS", "mono", 8, "#e9efe2", extra='letter-spacing=".8" opacity=".6"')
    for k, a in enumerate(d["activity"]):
        y = 78 + k * 52
        s.add(f'<rect x="17" y="{y}" width="138" height="46" rx="10" fill="#fff" fill-opacity=".13"/>')
        s.text(26, y + 16, ellipsize(a["repo"], "bodyb", 11, 80), "bodyb", 11, "#e9efe2")
        s.text(147, y + 16, f"{a['date'].day}/{a['date'].month:02d}", "mono", 8.5, "#e9efe2", "end", 'opacity=".6"')
        s.text(26, y + 34, ellipsize(a["msg"], "body", 10.5, 120), "body", 10.5, "#e9efe2", extra='opacity=".9"')
    s.add("</g>")
    s.add("</g>")
    s.save("passeport.svg")


# ---------------------------------------------------------------- 2. le carnet : la stack
STACK = [  # (catégorie, page, [(techno, fond, texte)])
    ("Langages", 0, [("HTML", "#e34f26", "#fff"), ("CSS", "#663399", "#fff"), ("JavaScript", "#f7df1e", "#2b2600"), ("TypeScript", "#3178c6", "#fff"),
                     ("Python", "#3776ab", "#fff"), ("PHP", "#777bb4", "#fff"), ("C", "#a8b9cc", "#1b2533")]),
    ("Bases de données", 0, [("MySQL", "#4479a1", "#fff"), ("PostgreSQL", "#336791", "#fff")]),
    ("Frameworks & librairies", 1, [("React", "#61dafb", "#0b2a33"), ("Angular", "#dd0031", "#fff"), ("Node.js", "#5fa04e", "#fff"),
                                    ("Vite", "#646cff", "#fff"), ("Electron", "#47848f", "#fff"), ("Spring Boot", "#6db33f", "#fff")]),
    ("Outils & OS", 1, [("Git", "#f05032", "#fff"), ("VS Code", "#007acc", "#fff"), ("Docker", "#2496ed", "#fff"), ("Ubuntu", "#e95420", "#fff")]),
]


PAGES = [("Compétences", "PAGE 1 · LANGAGES & DONNÉES"), ("Au quotidien", "PAGE 2 · FRAMEWORKS & OUTILS")]


def carnet():
    """Le carnet ouvert du portfolio : pages pointillées, spirale, titres manuscrits, étiquettes à ombre décalée."""
    W, PW, PH = 1128, 550, 392
    s = Svg(1200, PH + 28 + 60, "Stack : " + ", ".join(t for _, _, items in STACK for t, _, _ in items))
    wood(s)
    s.defs.append('<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse" x="11" y="11"><circle cx="11" cy="11" r="1.15" fill="#d6d3c9"/></pattern>')
    s.add(f'<g transform="translate(36 30) rotate(-.4)"><rect width="{W}" height="{PH + 28}" rx="12" fill="#1c2638" filter="url(#sh)"/>')
    for page in (0, 1):
        px = 14 + page * PW
        s.add(f'<rect x="{px}" y="14" width="{PW}" height="{PH}" rx="{4 if page == 0 else 2}" fill="#fbfaf5"/>'
              f'<rect x="{px}" y="14" width="{PW}" height="{PH}" fill="url(#dots)"/>')
        x0 = px + 40
        title, cap = PAGES[page]
        s.text(x0, 76, title, "hand", 46, "#1c2638")
        s.text(x0, 100, cap, "mono", 11.5, "#6b6e72", extra='letter-spacing=".7"')
        y = 150
        for cat, pg, items in STACK:
            if pg != page:
                continue
            s.text(x0, y, cat, "hand", 28, "#2b5fd9")
            x, yy = x0, y + 16
            for it, col, _ in items:
                w = measure(it, "mono", 15) + 40
                if x + w > px + PW - 40:
                    x, yy = x0, yy + 44
                # étiquette : fond blanc, bord noir, ombre pleine décalée de 2 px (comme .tags span)
                s.add(f'<rect x="{x + 2.5:.0f}" y="{yy + 2.5:.0f}" width="{w:.0f}" height="32" rx="4" fill="#1d1f22"/>'
                      f'<rect x="{x:.0f}" y="{yy:.0f}" width="{w:.0f}" height="32" rx="4" fill="#fff" stroke="#1d1f22" stroke-width="1.6"/>'
                      f'<circle cx="{x + 15:.0f}" cy="{yy + 16:.0f}" r="4.5" fill="{col}"/>')
                s.text(x + 27, yy + 21, it, "mono", 15, "#1d1f22")
                x += w + 10
            y = yy + 84
    # spirale au centre
    for k in range(int((PH - 30) / 30) + 1):
        s.add(f'<rect x="{14 + PW - 14}" y="{40 + k * 30}" width="28" height="6" rx="3" fill="#c4c8ce"/>')
    s.add("</g></g>")
    s.save("stack.svg")


# ---------------------------------------------------------------- 3. le dossier kraft : les repos épinglés, dans un seul SVG
# couleurs de bandeau (fond, texte, filet) : celles du portfolio, puis une palette tournante pour les prochains repos
REPO_STYLE = {"kairos": ("#2e372d", "#e9efe2", "#6f8a63"), "Focus": ("#202020", "#f4f4f2", "#9a9a9a"),
              "box-box": ("#1b130e", "#f1e4cf", "#e4572e"), "portfolio": ("#8a6a3f", "#fbf3e4", "#dcb676")}
PALETTE = [("#1f3b73", "#eef2fb", "#2b5fd9"), ("#27344a", "#f1efe8", "#7d5bd0"), ("#5b2a1e", "#fbeee6", "#e4572e"), ("#2f3b38", "#e9efe2", "#f0a81c")]
LANG_COLORS = {"TypeScript": "#3178c6", "JavaScript": "#f1e05a", "CSS": "#663399", "HTML": "#e34c26", "Kotlin": "#A97BFF", "Java": "#b07219",
               "Python": "#3572A5", "Shell": "#89e051", "PHP": "#4F5D95", "C": "#555555"}


def style_of(name, i):
    return REPO_STYLE.get(name, PALETTE[i % len(PALETTE)])


FW = 548  # largeur d'une fiche


def fiche_lines(r):
    return wrap(r["desc"], "body", 16.5, FW - 60)[:3] or [""]


def line_y(k):
    """Ligne k du papier ligné de la fiche (coordonnées de la feuille)."""
    return 76 + 28 * k


def fiche_height(r):
    return line_y(2 + len(fiche_lines(r)) + 4) + 22


def leader(s, x0, x1, y, dt, dd, ink="#1d1f22"):
    """Ligne « Stars ........ 2 », comme les .fields du portfolio."""
    s.text(x0, y, dt, "mono", 13, "#6b6e72")
    s.text(x1, y, dd, "mono", 13, ink, "end")
    a, b = x0 + measure(dt, "mono", 13) + 8, x1 - measure(dd, "mono", 13) - 8
    if b > a:
        s.add(f'<line x1="{a:.0f}" y1="{y - 3}" x2="{b:.0f}" y2="{y - 3}" stroke="#6b6e72" stroke-width="1.2" stroke-dasharray="1 3.2" stroke-linecap="round"/>')


def draw_fiche(s, r, x, y, i, H):
    """Une fiche du dossier : onglet de couleur, bandeau, papier ligné, tampon et champs à pointillés."""
    bg, fg, accent = style_of(r["name"], i)
    langs = r["langs"]
    tot = sum(langs.values()) or 1
    main = next(iter(langs), "—")
    p = r["pushed"]
    s.add(f'<g transform="translate({x} {y}) rotate({[-.7, .6, .5, -.5][i % 4]})"><g class="lift" style="animation-delay:-{i * 1.7:.1f}s">')
    # onglet qui dépasse au-dessus de la fiche
    tab = f"{r['name']}"
    tw = measure(tab, "bodyb", 13) + measure(" · repo", "mono", 11) + 28
    s.add(f'<path d="M0 31V9Q0 0 9 0H{tw - 9:.0f}Q{tw:.0f} 0 {tw:.0f} 9V31Z" fill="{bg}" filter="url(#shs)"/>')
    s.text(12, 21, tab, "bodyb", 13, fg)
    s.text(12 + measure(tab, "bodyb", 13) + 6, 21, "· repo", "mono", 11, fg, extra='opacity=".7"')
    # la feuille
    s.add(f'<g transform="translate(0 30)" filter="url(#sh)"><path d="M0 2Q0 0 2 0H{FW - 8}Q{FW} 0 {FW} 8V{H - 8}Q{FW} {H} {FW - 8} {H}H8Q0 {H} 0 {H - 8}Z" fill="#fbfaf6"/>'
          f'<path d="M0 2Q0 0 2 0H{FW - 8}Q{FW} 0 {FW} 8V36H0Z" fill="{bg}"/>')
    s.text(24, 23, f"{main.upper()} · {'PRIVÉ' if r['private'] else 'PUBLIC'}", "mono", 11.5, fg, extra='letter-spacing=".9"')
    s.text(FW - 24, 23, f"MAJ {p.day} {MOIS_COURTS[p.month - 1].upper()} {p.year}", "mono", 11.5, fg, "end", 'letter-spacing=".9"')
    # papier ligné (un trait tous les 28 px, comme .content)
    for ly in range(36 + 40, H - 10, 28):
        s.add(f'<rect x="0" y="{ly}" width="{FW}" height="1" fill="#e3e0d6"/>')
    s.add(f'<rect x="22" y="58" width="{measure(r["name"], "display", 30, -.8) + 10:.0f}" height="40" fill="#fbfaf6"/>')
    s.text(24, 92, r["name"], "display", 30, "#1d1f22", extra='letter-spacing="-.8"')
    desc = fiche_lines(r)
    for k, line in enumerate(desc):  # chaque ligne posée sur un trait du papier
        s.text(24, line_y(2 + k) - 6, line, "body", 16.5, "#1d1f22")
    top3 = [f"{l} {100 * n / tot:.0f} %" for l, n in list(langs.items())[:2] if n / tot >= .01]
    for k, (dt, dd) in enumerate([("Langages", " · ".join(top3) or "—"), ("Stars", str(r["stars"])), ("Forks", str(r["forks"])),
                                  ("Mis à jour", f"{p.day} {MOIS[p.month - 1]} {p.year}")]):
        leader(s, 24, FW - 24, line_y(2 + len(desc) + k) - 7, dt, dd)
    # tampon rouge
    s.add(f'<g transform="translate({FW - 92} 86) rotate(-12)" opacity=".82"><rect x="-44" y="-15" width="88" height="28" rx="4" fill="none" stroke="#c2362b" stroke-width="3"/>')
    s.text(0, 5, "ÉPINGLÉ", "monob", 13, "#c2362b", "middle", 'letter-spacing="1.8"')
    s.add("</g></g></g></g>")


CUT = 66          # hauteur de la bande du haut (onglets), découpée en morceaux cliquables
TAB_X0, TAB_W = 40, 132
FOLDER_DEFS = ('<linearGradient id="kback" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c39a5b"/><stop offset="1" stop-color="#a98146"/></linearGradient>'
               '<linearGradient id="kfront" x1=".45" y1="0" x2=".55" y2="1"><stop offset="0" stop-color="#dcb676"/><stop offset="1" stop-color="#c9a160"/></linearGradient>')


def back_panel(s, H):
    """Dos du dossier (.f-back) avec son onglet titré (.f-tab) à droite."""
    s.add(f'<path d="M0 62Q0 50 4 50H860V20Q860 8 872 8H1188Q1200 8 1200 20V{H}H0Z" fill="url(#kback)"/>')


def bande(d):
    """La bande du haut du dossier, en morceaux : marge gauche, un onglet par repo, puis le reste.
    Chaque morceau est un SVG à part pour que chaque onglet ait son propre lien dans le README."""
    names = d["pinned_order"][:6]
    edges = [0] + [TAB_X0 + k * TAB_W for k in range(len(names) + 1)] + [1200]
    pieces = []
    for old in OUT.glob("dossier-*.svg"):
        old.unlink()
    for k in range(len(edges) - 1):
        x0, x1 = edges[k], edges[k + 1]
        if k == 0:
            kind, title = "bord", "Dossier Repos"
        elif k <= len(names):
            kind, title = names[k - 1], f"Onglet du repo {names[k - 1]} : ouvrir le repo"
        else:
            kind, title = "fond", "Repos épinglés : voir tous mes repos"
        s = Svg(x1 - x0, CUT, title)
        s.vx = x0
        s.defs.append(SHADOW + FOLDER_DEFS + f'<clipPath id="frame"><rect width="1200" height="{CUT + 40}" rx="18"/></clipPath>')
        s.add('<g clip-path="url(#frame)">')
        back_panel(s, CUT + 40)
        if k == len(edges) - 2:
            s.text(884, 36, "REPOS ÉPINGLÉS · ELICOPTER-NC", "monob", 12, "#3d2a12", extra='letter-spacing=".7"')
        for i, name in enumerate(names):
            tx = TAB_X0 + i * TAB_W
            if tx + 128 <= x0 or tx >= x1:
                continue
            bg, fg, _ = style_of(name, i)
            s.add(f'<path d="M{tx} {CUT + 10}V30Q{tx} 22 {tx + 8} 22H{tx + 120}Q{tx + 128} 22 {tx + 128} 30V{CUT + 10}Z" fill="{bg}" '
                  'stroke="#fff" stroke-opacity=".22" stroke-width="1.5"/>')
            lab = ellipsize(name, "monob", 11.5, 96)
            s.text(tx + 56, 46, lab, "monob", 11.5, fg, "middle", 'letter-spacing=".4"')
            s.text(tx + 56 + measure(lab, "monob", 11.5, .4) / 2 + 10, 46, "↗", "monob", 11.5, fg, extra='opacity=".75"')
        s.add("</g>")
        f = f"dossier-{k:02d}.svg"
        s.save(f)
        pct = 100 * (x1 - x0) / 1200 - (.05 if kind == "fond" else 0)  # marge anti-retour à la ligne
        # la marge et le fond mènent à tous mes repos (sans lien, GitHub ferait pointer l'image vers elle-même)
        href = f"https://github.com/{USER}" + ("?tab=repositories" if kind in ("bord", "fond") else f"/{kind}")
        pieces.append(f'<a href="{href}"><img src="assets/{f}" width="{pct:.3f}%" align="top" alt="{esc(title)}" /></a>')
    return "".join(pieces)  # sans espace entre les images : la bande reste d'un seul tenant


def dossier(d):
    repos = [d["pinned"][n] for n in d["pinned_order"]]
    rows = [repos[k:k + 2] for k in range(0, len(repos), 2)]
    heights = [max(fiche_height(r) for r in row) for row in rows]
    top, gap, W = 226, 40, 1200
    H = top + sum(h + 30 for h in heights) + gap * (len(rows) - 1) + 44
    s = Svg(W, H - CUT, "Repos épinglés : " + ", ".join(f"{r['name']} ({r['desc']})" for r in repos))
    s.defs.append(SHADOW + FOLDER_DEFS +
                  '<filter id="up" x="-5%" y="-20%" width="110%" height="140%"><feDropShadow dx="0" dy="-6" stdDeviation="9" flood-color="#000" flood-opacity=".2"/></filter>'
                  f'<clipPath id="frame"><path d="M0 {CUT}H{W}V{H - 18}Q{W} {H} {W - 18} {H}H18Q0 {H} 0 {H - 18}Z"/></clipPath>')
    s.css.append("@keyframes lift{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}.lift{animation:lift 6s ease-in-out infinite}")
    s.add(f'<g transform="translate(0 -{CUT})"><g clip-path="url(#frame)">')
    back_panel(s, H)
    # bas des onglets, cachés derrière le rabat
    for i, name in enumerate(d["pinned_order"][:6]):
        s.add(f'<rect x="{TAB_X0 + i * TAB_W}" y="{CUT}" width="128" height="10" fill="{style_of(name, i)[0]}"/>')
    # rabat avant (.f-front) : dégradé kraft, liseré clair en haut, ombre vers le haut
    s.add(f'<g filter="url(#up)"><path d="M0 76Q0 66 10 66H1190Q1200 66 1200 76V{H}H0Z" fill="url(#kfront)"/></g>'
          '<path d="M2 70Q4 66 10 66H1190Q1196 66 1198 70" fill="none" stroke="#ead1a0" stroke-width="2.5"/>')
    # étiquette (.label)
    s.add('<g transform="translate(44 94) rotate(-1.2)" filter="url(#shs)"><rect width="440" height="104" rx="3" fill="#fbfaf6"/>')
    s.text(20, 27, f"DOSSIER · {len(repos)} FICHE{'S' if len(repos) > 1 else ''}", "mono", 11, "#6b6e72", extra='letter-spacing=".9"')
    s.text(20, 66, "Repos", "display", 36, "#1d1f22", extra='letter-spacing="-1"')
    s.text(20, 90, "Les projets que j'ai épinglés sur mon profil.", "body", 15, "#6b6e72")
    s.add("</g>")
    s.text(1156, 170, "↖ clique sur un onglet pour ouvrir le repo", "mono", 12.5, "#3d2a12", "end")
    s.text(1156, 192, "ou sur le dossier pour tous les voir", "mono", 12.5, "#3d2a12", "end", 'opacity=".75"')
    y = top
    for ri, row in enumerate(rows):
        for ci, r in enumerate(row):
            x = 40 if len(row) == 2 else 326
            draw_fiche(s, r, x + ci * 572, y, ri * 2 + ci, heights[ri])
        y += heights[ri] + 30 + gap
    s.add("</g></g>")
    s.save("repos.svg")


def readme_dossier(d):
    """Réécrit le bloc du dossier dans le README (entre deux marqueurs) : la bande d'onglets cliquables, puis le dossier."""
    for old in OUT.glob("lien-repo-*.svg"):  # anciennes étiquettes sous le dossier
        old.unlink()
    block = (bande(d) + "\n" + f'<a href="https://github.com/{USER}?tab=repositories"><img src="assets/repos.svg" width="100%" align="top" '
             'alt="Dossier de mes repos épinglés" /></a>')
    readme = ROOT / "README.md"
    txt = readme.read_text(encoding="utf-8")
    a, b = "<!-- dossier:start -->", "<!-- dossier:end -->"
    if a in txt and b in txt:
        txt = txt[:txt.index(a) + len(a)] + "\n" + block + "\n" + txt[txt.index(b):]
        readme.write_text(txt, encoding="utf-8")


# ---------------------------------------------------------------- 4. les stats : le calendrier du portfolio, les post-its, les langages
# mêmes teintes que le grand calendrier du portfolio (.cal-big .cm-day[data-l])
DAY_BG = {"NONE": "#fff", "FIRST_QUARTILE": "#fdf1d2", "SECOND_QUARTILE": "#fbe3a4", "THIRD_QUARTILE": "#f7cc6a", "FOURTH_QUARTILE": "#f2b53a"}
JOURS = ["LUN.", "MAR.", "MER.", "JEU.", "VEN.", "SAM.", "DIM."]


def series(days):
    """Série actuelle (un jour sans contribution aujourd'hui ne la casse pas encore) et plus longue série."""
    longest = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    cur = 0
    rest = days[:-1] if days and not days[-1][1] else days
    for _, n in reversed(rest):
        if not n:
            break
        cur += 1
    return cur, longest


def calendrier(s, d, ox, oy, W):
    """Page du mois en cours, comme le calendrier en grand du portfolio : cases à filet, jour en gras, week-end en rouge."""
    cal = d["calendar"]
    level = {c["date"]: c["contributionLevel"] for w in cal["weeks"] for c in w["contributionDays"]}
    count = {c["date"]: c["contributionCount"] for w in cal["weeks"] for c in w["contributionDays"]}
    days = sorted(count.items())
    cur, longest = series(days)
    today = date.fromisoformat(days[-1][0])
    first = today.replace(day=1)
    lead = first.weekday()  # 0 = lundi
    nxt = date(today.year + today.month // 12, today.month % 12 + 1, 1)
    ndays = (nxt - first).days
    nrows = -(-(lead + ndays) // 7)
    px, gap = 30, 4
    cw = (W - 2 * px - 6 * gap) / 7
    rh = 62
    gy = 132
    Hc = gy + nrows * (rh + gap) + 54
    s.add(f'<g transform="translate({ox} {oy}) rotate(-.8)" filter="url(#sh)"><rect width="{W}" height="{Hc}" rx="4" fill="#fdfcf8"/>')
    for k in range(12):  # anneaux de la spirale
        s.add(f'<rect x="{W * .06 + k * (W * .88 - 9) / 11:.1f}" y="-12" width="9" height="26" rx="5" fill="url(#ring)"/>')
    s.text(px, 72, MOIS[today.month - 1].capitalize(), "display", 34, "#b3261e", extra='letter-spacing="-.6"')
    s.text(px + measure(MOIS[today.month - 1].capitalize(), "display", 34, -.6) + 14, 72, str(today.year), "display", 24, "#9aa0a8")
    month_sum = sum(n for k, n in count.items() if k.startswith(today.strftime("%Y-%m")))
    s.text(W - px, 72, f"{month_sum} ce mois-ci", "mono", 13, "#55595f", "end")
    s.add(f'<rect x="{px}" y="84" width="{W - 2 * px}" height="3" fill="#1b1d20"/>')
    for i, j in enumerate(JOURS):
        s.text(px + i * (cw + gap) + 6, 116, j, "monob", 11, "#b3261e" if i >= 5 else "#55595f", extra='letter-spacing=".8"')
    for idx in range(nrows * 7):
        dt = first + timedelta(days=idx - lead)
        x, y = px + (idx % 7) * (cw + gap), gy + (idx // 7) * (rh + gap)
        out = dt.month != today.month
        we = idx % 7 >= 5
        if out:
            s.text(x + 7, y + 24, str(dt.day), "display", 16, "#c9ccd1")
            continue
        lv = level.get(dt.isoformat(), "NONE") if dt <= today else "NONE"
        s.add(f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{rh}" rx="2" fill="{DAY_BG[lv]}"/>'
              f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="2" fill="{"#e0900f" if lv != "NONE" else "#e3e1da"}"/>')
        s.text(x + 7, y + 24, str(dt.day), "display", 16, "#b3261e" if we else ("#1b1d20" if dt <= today else "#9aa0a8"))
        n = count.get(dt.isoformat(), 0)
        if n and dt <= today:
            s.text(x + 7, y + rh - 9, f"{n} contrib.", "mono", 10.5, "#7a4a06")
        if dt == today:  # entouré au feutre, comme .cm-day.today::after
            s.add(f'<ellipse class="today" cx="{x + 19:.1f}" cy="{y + 18}" rx="18" ry="15" transform="rotate(-8 {x + 19:.1f} {y + 18})" '
                  'fill="none" stroke="#e4572e" stroke-width="2.5"/>')
    fy = gy + nrows * (rh + gap) + 30
    s.text(px, fy, f"{cal['totalContributions']} contributions sur un an", "bodyb", 15, "#1b1d20")
    s.text(W - px, fy, f"série actuelle {cur} j · record {longest} j", "body", 15, "#55595f", "end")
    s.add("</g>")
    return Hc


def langages_card(s, d, ox, oy, W):
    """Fiche papier sobre : barre empilée + liste, typographie du portfolio."""
    langs = d["languages"]
    tot = sum(n for _, n in langs) or 1
    top = langs[:6]
    rest = sum(n for _, n in langs[6:])
    if rest:
        top.append(("Autres", rest))
    Hc = 120 + len(top) * 40 + 34
    s.add(f'<g transform="translate({ox} {oy}) rotate(.8)" filter="url(#sh)"><rect width="{W}" height="{Hc}" rx="4" fill="#fbfaf6"/>')
    s.text(24, 34, "LES PLUS UTILISÉS", "mono", 10.5, "#6b6e72", extra='letter-spacing="1"')
    s.text(24, 64, "Langages", "display", 24, "#1d1f22", extra='letter-spacing="-.6"')
    s.add(f'<rect x="24" y="78" width="{W - 48}" height="2.5" fill="#1b1d20"/>')
    # barre empilée
    s.add(f'<clipPath id="lstk"><rect x="24" y="96" width="{W - 48}" height="10" rx="5"/></clipPath><g clip-path="url(#lstk)">')
    x = 24.0
    for lang, n in top:
        w = (W - 48) * n / tot
        s.add(f'<rect class="seg" x="{x:.1f}" y="96" width="{w + .5:.1f}" height="10" fill="{LANG_COLORS.get(lang, "#9aa0a8")}"/>')
        x += w
    s.add("</g>")
    maxp = top[0][1] / tot if top else 1
    for i, (lang, n) in enumerate(top):
        y = 140 + i * 40
        pct = n / tot
        col = LANG_COLORS.get(lang, "#9aa0a8")
        s.add(f'<rect x="24" y="{y - 11}" width="10" height="10" rx="2" fill="{col}"/>')
        s.text(44, y, lang, "bodyb", 15, "#1d1f22")
        s.text(W - 24, y, f"{100 * pct:.1f} %", "monob", 12.5, "#3c4046", "end")
        s.add(f'<rect x="44" y="{y + 9}" width="{W - 68}" height="2" fill="#ece8de"/>'
              f'<rect class="fill" style="animation-delay:{.1 * i:.1f}s" x="44" y="{y + 9}" width="{max(3, (W - 68) * pct / maxp):.1f}" height="2" fill="{col}"/>')
    s.text(24, Hc - 18, f"{len(langs)} langages · tous mes repos publics", "mono", 10, "#6b6e72")
    s.add("</g>")
    return Hc


def stats(d):
    W = 1200
    s = Svg(W, 10, "")  # hauteur fixée plus bas
    langs = d["languages"]
    tot = sum(n for _, n in langs) or 1
    s.title = (f"{d['calendar']['totalContributions'] if d['calendar'] else '?'} contributions sur un an, {d['commits']} commits, "
               f"{d['stars']} stars, {d['repos']} repos. Langages : " + ", ".join(f"{l} {100 * n / tot:.0f} %" for l, n in langs[:6]))
    # le bois se dessine en dernier (puis passe dessous) : sa hauteur dépend du calendrier et de la fiche
    s.css.append("@keyframes ringp{0%,100%{stroke-opacity:1}50%{stroke-opacity:.3}}.today{animation:ringp 1.8s ease-in-out infinite}"
                 "@keyframes grow{from{transform:scaleX(0)}}.fill{animation:grow 1.2s cubic-bezier(.2,.8,.2,1) both;transform-box:fill-box;transform-origin:left center}")
    s.defs.append('<linearGradient id="ring" x1="0" x2="1"><stop offset="0" stop-color="#8b9098"/><stop offset=".5" stop-color="#e2e4e7"/><stop offset="1" stop-color="#8b9098"/></linearGradient>')
    hc =calendrier(s, d, 34, 48, 720) if d["calendar"] else 0
    # post-its
    items = [("Commits", d["commits"] if d["commits"] is not None else "—", "sur un an", "#ffe27a", "#3a2f05", -4),
             ("Stars", d["stars"], "sur mes repos", "#ffb8c9", "#4a1424", 3),
             ("Repos", d["repos"], "publics", "#bfe6c8", "#163a22", -2)]
    for i, (title, n, sub, bg, ink, r) in enumerate(items):
        s.add(f'<g transform="translate({790 + i * 128} {44 + (i % 2) * 8}) rotate({r})" filter="url(#sh)">'
              f'<path d="M0 0H118V110L108 120H0Z" fill="{bg}"/>')
        s.text(12, 28, title, "hand", 23, ink)
        s.add(f'<rect x="12" y="33" width="{measure(title, "hand", 23):.0f}" height="2" fill="{ink}"/>')
        s.text(59, 80, str(n), "display", 34 if len(str(n)) < 4 else 26, ink, "middle", 'letter-spacing="-1"')
        s.text(59, 106, sub, "hand", 16, ink, "middle", 'opacity=".75"')
        s.add("</g>")
    hl = langages_card(s, d, 790, 196, 370)
    H = max(48 + hc, 196 + hl) + 40
    s.h = H
    parts = s.parts
    s.parts = []
    wood(s)
    s.parts += parts
    s.add("</g>")
    s.save("stats.svg")


# ---------------------------------------------------------------- 5. contact : des stickers cliquables (un SVG par lien)
CONTACTS = [  # (fichier, texte, fond, encre, rotation)
    ("portfolio", "Mon portfolio →", "#ffcf5a", "#3a2600", -2),
]


def contacts():
    for key, text, bg, fg, r in CONTACTS:
        w = measure(text, "monob", 17) + 48
        s = Svg(round(w + 28), 72, text)
        s.defs.append(SHADOW)
        s.add(f'<g transform="translate({(w + 28) / 2:.0f} 34) rotate({r})" filter="url(#shs)"><rect x="{-w / 2:.0f}" y="-22" width="{w:.0f}" height="44" rx="22" fill="{bg}" stroke="#000" stroke-opacity=".08"/>')
        s.text(0, 6, text, "monob", 17, fg, "middle")
        s.add("</g>")
        s.save(f"contact-{key}.svg")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    data = github_data()
    passeport(data)
    carnet()
    dossier(data)
    readme_dossier(data)
    stats(data)
    contacts()
