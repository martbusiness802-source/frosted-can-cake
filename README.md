# frosted-can-cake — Amenda Cakes · Frosted Cake Can

Site vitrine bilingue (FR / EN) d'Amenda Cakes, Douala : canette 3D animée au défilement (Three.js + GSAP), les 4 saveurs, pack découverte et commande WhatsApp avec total automatique.

## Lancer en local
Ouvrir `index.html` dans un navigateur, ou :

```bash
npx serve .
```

## Mettre en ligne
Site statique d'un seul fichier : GitHub Pages, Netlify ou Vercel fonctionnent sans configuration.
Avec GitHub Pages : Settings → Pages → Branch `main` / `/ (root)`.

## Modifier
- Prix et saveurs : tableau `MENU` et sections `.sec` dans `index.html`
- Traductions anglaises : attributs `data-en` et objet `T`
- Numéro WhatsApp : rechercher `237654134482`
- Version anglaise directe : ajouter `#en` à l'URL

## Sécurité
- **En-têtes HTTP** (`netlify.toml` et `vercel.json`, identiques) : politique CSP qui n'autorise que les serveurs utilisés par le site, protection contre l'affichage dans une autre page (clickjacking), HTTPS forcé (HSTS), `nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- **Empreintes SRI** sur GSAP : si le fichier est modifié sur le CDN, le navigateur refuse de l'exécuter.
- **Three.js** : version figée (0.160.0) et source de secours (esm.sh) si jsDelivr est bloqué ou trop lent.
- **Formulaire** : le texte du client est nettoyé et limité à 500 caractères ; il ne sert qu'au lien WhatsApp et n'est jamais inséré dans la page.
- **Liens externes** : `rel="noopener noreferrer"`.
- **Faille à signaler** : `/.well-known/security.txt`.

Le plus important reste vos comptes : activez la **double authentification (2FA)** sur GitHub, Netlify et Vercel. Un site statique comme celui-ci ne se pirate presque jamais par le code, mais par un compte volé.

## Vérification automatique (Python)
```bash
python3 tools/verifier_site.py
```
Contrôle les en-têtes de sécurité, les empreintes SRI, les liens, les fichiers manquants, les clés secrètes oubliées et la cohérence de la CSP avec ce que la page charge. Il tourne aussi tout seul sur GitHub à chaque envoi (onglet *Actions*).

Changer l'adresse du site (aperçu WhatsApp/Facebook, Google) :
```bash
python3 tools/verifier_site.py --domaine https://votre-adresse.vercel.app
```

## Partage et référencement
- Aperçu WhatsApp/Facebook : `assets/og-image.jpg` et balises Open Graph.
- Google : données structurées (boulangerie, menu et prix), `sitemap.xml`, `robots.txt`.
- Ajout à l'écran d'accueil du téléphone : `site.webmanifest`.
- Page d'erreur aux couleurs du site : `404.html`.
- Vercel Speed Insights (version HTML) : actif seulement sur Vercel.

Si vous ajoutez un nouveau serveur externe (script, police, image), ajoutez-le dans la CSP de `netlify.toml` **et** de `vercel.json`, puis lancez `python3 tools/verifier_site.py`.
