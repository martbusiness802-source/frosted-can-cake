#!/usr/bin/env python3
"""Vérifie le site Frostedcan avant chaque mise en ligne (sécurité, liens, fichiers).

Utilisation :
    python3 tools/verifier_site.py                      # vérifie tout
    python3 tools/verifier_site.py --domaine https://frostedcan.vercel.app
                                                        # change l'adresse du site (partage, SEO), puis vérifie

Aucune connexion internet n'est nécessaire. Sortie 0 si tout va bien, 1 sinon.
Python 3.8 ou plus récent, bibliothèque standard uniquement.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

RACINE = Path(__file__).resolve().parent.parent
PAGES = ["index.html", "404.html"]
DOMAINE_ACTUEL = re.compile(r"https://[a-z0-9.-]+\.(?:netlify\.app|vercel\.app|github\.io|[a-z]{2,})(?=/)")
FICHIERS_DOMAINE = ["index.html", "robots.txt", "sitemap.xml"]

erreurs, avertissements = [], []


def erreur(msg):
    erreurs.append(msg)


def avert(msg):
    avertissements.append(msg)


class Analyse(HTMLParser):
    """Relève les scripts, feuilles de style, liens et images d'une page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.balises = []
        self._script = None
        self.scripts_inline = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.balises.append((tag, a))
        if tag == "script" and "src" not in a:
            self._script = {"type": a.get("type", ""), "texte": ""}

    def handle_data(self, data):
        if self._script is not None:
            self._script["texte"] += data

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.scripts_inline.append(self._script)
            self._script = None


def lire_csp():
    toml = (RACINE / "netlify.toml").read_text(encoding="utf-8")
    m = re.search(r'Content-Security-Policy = "([^"]+)"', toml)
    if not m:
        erreur("netlify.toml : pas de Content-Security-Policy")
        return {}
    csp = {}
    for directive in m.group(1).split(";"):
        morceaux = directive.split()
        if morceaux:
            csp[morceaux[0]] = morceaux[1:]
    return csp


def autorise(csp, directive, url):
    sources = csp.get(directive, csp.get("default-src", []))
    hote = "{0.scheme}://{0.netloc}".format(urlparse(url))
    return any(s == hote or (s.endswith("/") and url.startswith(s)) for s in sources)


def verifier_entetes():
    toml = (RACINE / "netlify.toml").read_text(encoding="utf-8")
    bloc = toml.split('for = "/*"', 1)[-1].split("[[headers]]", 1)[0]
    netlify = dict(re.findall(r'^\s+([A-Za-z-]+) = "(.*)"$', bloc, re.M))
    obligatoires = ["Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options",
                    "Referrer-Policy", "Permissions-Policy", "Strict-Transport-Security"]
    for nom in obligatoires:
        if nom not in netlify:
            erreur("netlify.toml : en-tête de sécurité manquant : " + nom)
    try:
        vercel = json.loads((RACINE / "vercel.json").read_text(encoding="utf-8"))
        tous = next(h for h in vercel["headers"] if h["source"] == "/(.*)")
        vercel_vals = {h["key"]: h["value"] for h in tous["headers"]}
        for nom, valeur in netlify.items():
            if vercel_vals.get(nom) != valeur:
                erreur("vercel.json : l'en-tête {} diffère de netlify.toml".format(nom))
    except (OSError, ValueError, StopIteration, KeyError) as e:
        erreur("vercel.json illisible ou incomplet : {}".format(e))
    csp = lire_csp()
    for directive, attendu in [("frame-ancestors", "'none'"), ("object-src", "'none'"), ("base-uri", "'self'")]:
        if attendu not in csp.get(directive, []):
            erreur("CSP : {} devrait valoir {}".format(directive, attendu))
    return csp


def verifier_page(nom, csp):
    chemin = RACINE / nom
    if not chemin.exists():
        erreur(nom + " : fichier absent")
        return
    texte = chemin.read_text(encoding="utf-8")
    page = Analyse()
    page.feed(texte)

    for tag, a in page.balises:
        url = a.get("src") or (a.get("href") if tag in ("link", "a") else None)
        if not url:
            continue
        externe = url.startswith(("http://", "https://"))
        if url.startswith("http://"):
            erreur("{} : lien non sécurisé (http) : {}".format(nom, url))
        # scripts classiques venus d'ailleurs : empreinte SRI obligatoire
        if tag == "script" and externe and a.get("type") != "module":
            if not a.get("integrity", "").startswith(("sha384-", "sha512-")):
                erreur("{} : script externe sans empreinte integrity : {}".format(nom, url))
            if a.get("crossorigin") != "anonymous":
                erreur("{} : script externe sans crossorigin=\"anonymous\" : {}".format(nom, url))
            if not autorise(csp, "script-src", url):
                erreur("{} : la CSP bloquerait le script {}".format(nom, url))
        if tag == "link" and a.get("rel") == "stylesheet" and externe and not autorise(csp, "style-src", url):
            erreur("{} : la CSP bloquerait la feuille de style {}".format(nom, url))
        # liens qui ouvrent un nouvel onglet
        if tag == "a" and a.get("target") == "_blank":
            rel = (a.get("rel") or "").split()
            if "noopener" not in rel or "noreferrer" not in rel:
                erreur("{} : lien _blank sans rel=\"noopener noreferrer\" : {}".format(nom, url))
        # fichiers du site
        if not externe and not url.startswith(("#", "mailto:", "tel:", "data:", "blob:")) and url not in ("/", "./"):
            local = url.split("#")[0].split("?")[0].lstrip("/")
            if local.startswith("_vercel/"):
                continue  # créé par Vercel au déploiement
            if local and not (RACINE / local).exists():
                erreur("{} : fichier introuvable : {}".format(nom, url))

    for s in page.scripts_inline:
        if s["type"] == "application/ld+json":
            try:
                json.loads(s["texte"])
            except ValueError as e:
                erreur("{} : données structurées JSON-LD invalides : {}".format(nom, e))
        if s["type"] == "module":
            for url in re.findall(r"['\"](https://[^'\"]+)['\"]", s["texte"]):
                if ("import(" in s["texte"] or "from '" in s["texte"]) and not autorise(csp, "script-src", url):
                    if urlparse(url).netloc not in ("wa.me",):
                        erreur("{} : la CSP bloquerait le module {}".format(nom, url))
        if re.search(r"\beval\s*\(|new Function\s*\(", s["texte"]):
            erreur("{} : eval/new Function détecté dans un script".format(nom))

    # clés ou mots de passe oubliés dans le code
    for motif in [r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{30,}", r"sk_(live|test)_[A-Za-z0-9]{10,}",
                  r"(?i)(password|mot_de_passe|api[_-]?key|secret)\s*[:=]\s*['\"][^'\"]{6,}"]:
        if re.search(motif, texte):
            erreur("{} : ce qui ressemble à une clé secrète a été trouvé (motif {})".format(nom, motif))

    if nom == "index.html":
        og = re.search(r'<meta property="og:image" content="([^"]+)"', texte)
        if not og:
            avert("index.html : pas d'image de partage og:image")
        elif not (RACINE / urlparse(og.group(1)).path.lstrip("/")).exists():
            erreur("index.html : l'image de partage n'existe pas : " + og.group(1))


def verifier_divers():
    for fichier in ["site.webmanifest", "vercel.json"]:
        try:
            json.loads((RACINE / fichier).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            erreur("{} invalide : {}".format(fichier, e))
    for fichier in ["robots.txt", "sitemap.xml", ".well-known/security.txt", "404.html"]:
        if not (RACINE / fichier).exists():
            avert(fichier + " manquant")
    gros = [p for p in RACINE.rglob("*") if p.is_file() and ".git" not in p.parts and p.stat().st_size > 2_000_000]
    for p in gros:
        avert("fichier lourd (plus de 2 Mo), à alléger pour les téléphones : " + str(p.relative_to(RACINE)))


def changer_domaine(nouveau):
    nouveau = nouveau.rstrip("/")
    if not re.match(r"^https://[a-z0-9.-]+$", nouveau):
        sys.exit("Adresse invalide : écrivez par exemple https://frostedcan.vercel.app")
    for nom in FICHIERS_DOMAINE:
        chemin = RACINE / nom
        texte = chemin.read_text(encoding="utf-8")
        # ne remplace que l'adresse du site dans les balises de partage/SEO, pas les CDN
        nouveau_texte = re.sub(
            r"(og:url\" content=\"|og:image\" content=\"|canonical\" href=\"|\"url\":\"|\"image\":\"|Sitemap: |<loc>)" + DOMAINE_ACTUEL.pattern,
            lambda m: m.group(1) + nouveau, texte)
        if nouveau_texte != texte:
            chemin.write_text(nouveau_texte, encoding="utf-8")
            print("adresse mise à jour dans", nom)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--domaine", help="nouvelle adresse du site, ex. https://frostedcan.vercel.app")
    args = p.parse_args()
    if args.domaine:
        changer_domaine(args.domaine)

    csp = verifier_entetes()
    for nom in PAGES:
        verifier_page(nom, csp)
    verifier_divers()

    for a in avertissements:
        print("⚠️  " + a)
    for e in erreurs:
        print("❌ " + e)
    if erreurs:
        print("\n{} problème(s) à corriger avant la mise en ligne.".format(len(erreurs)))
        return 1
    print("✅ Site vérifié : sécurité, liens et fichiers en ordre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
