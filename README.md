# COFRAP — PoC d'authentification serverless

> Compagnie Française de Réalisation d'Applicatifs Professionnels  
> Génération automatique de comptes (mot de passe 24 car. + 2FA TOTP), rotation 6 mois.  
> Stack : **OpenFaaS Community** sur **Kubernetes Docker Desktop**, fonctions **Python**, base **PostgreSQL**, frontend **FastAPI**.

## Architecture

```
Utilisateur ─▶ Ingress Traefik ─▶ Frontend FastAPI ─▶ OpenFaaS Gateway ─▶ ┌ generate-password ┐
                                                                          ├ generate-2fa       ├─▶ PostgreSQL (table users)
deploy/               # OpenFaaS, PostgreSQL (Helm chart + manifests)
```

| Fonction | Rôle | Entrée | Sortie |
|---|---|---|---|
| `generate-password` | Mot de passe 24 car. (hash bcrypt) + QR code | `username` | `password`, `qrcode`, `gendate` (400/500) |
| `generate-2fa` | Secret TOTP chiffré (Fernet) + QR otpauth | `username` | `qrcode`, `gendate` (400/404/500) |
| `authenticate` | login + mot de passe + 2FA, expiration 6 mois | `username,password,totp_code` | `{authenticated, expired}` (200/401/404) |

Table `users` : `id, username, password, mfa, gendate, expired`. Expiration = 6 mois (15 552 000 s).

## Arborescence

```
functions/            # 3 fonctions OpenFaaS (Python)
  common/             # code partagé (db, crypto, qr) testable
  generate-password/  generate-2fa/  authenticate/
  stack.yml           # définition OpenFaaS
frontend/             # FastAPI : 5 routes (/, /create, /login, /renew, /qrcodes)
deploy/               # OpenFaaS, PostgreSQL (Helm chart + manifests)
tests/                # pytest : unitaires + intégration end-to-end (15 tests)
```

```markdown
# COFRAP — PoC d'authentification serverless

Compagnie Française de Réalisation d'Applicatifs Professionnels — preuve de concept
pour la génération automatique de comptes (mot de passe 24 car., 2FA TOTP) avec
rotation / expiration après 6 mois.

**Stack technique officielle (imposée/recommandée par le client)**
| Composant | Technologie | Justification |
|---|---|---|
| Langage | Python 3.11+ | Recommandé COFRAP ; libs sécurité matures |
| Kubernetes | Kubernetes Docker Desktop | Simple à activer sur Windows, accessible via `kubectl` |
| Serverless | OpenFaaS Community | Scale to Zero, intégration native Kubernetes/Helm |
| Base de données | PostgreSQL | ACID, chiffrement avancé, psycopg2 |
| Frontend | FastAPI + Jinja2 | Cohérence Python, Swagger auto, rapide |
| Déploiement | Helm | Automatise OpenFaaS & PostgreSQL, rollbacks natifs |
| Conteneurisation | Docker | Prérequis OpenFaaS, standard industrie |

Stack principal
- Frontend: FastAPI (dossier `frontend/`)
- Fonctions: OpenFaaS Python functions (dossier `functions/`)
- Base de données: PostgreSQL (table `users`)

Architecture
Utilisateur → Ingress (Traefik) → Frontend FastAPI → OpenFaaS Gateway → { generate-password, generate-2fa, authenticate } → PostgreSQL (table users)
```

Résumé des fonctions
- `generate-password`: génère un mot de passe de `PASSWORD_LENGTH` (24) caractères, stocke le `bcrypt` hash et renvoie un QR (PNG base64) du mot de passe.
- `generate-2fa`: génère un secret TOTP (base32), chiffre le secret avec Fernet (`totp-encryption-key`), stocke `mfa` chiffré et renvoie un QR otpauth (PNG base64).
- `authenticate`: vérifie `username` + `password` + `totp_code`, gère l'expiration (`SIX_MONTHS_SECONDS`) et peut marquer un compte `expired`.

Table `users` (attendue): `id, username, password, mfa, gendate, expired`.

Arborescence importante

```
functions/
  common/                # code partagé (DB, crypto, QR) testable
  generate-password/
  generate-2fa/
  authenticate/
  stack.yml              # définition OpenFaaS
frontend/                # FastAPI app (templates + static)
deploy/                  # scripts & manifests Kubernetes / OpenFaaS (helm, postgres chart)
tests/                   # pytest (unit + integration)
```

Fichiers à lire en priorité
- `functions/common/cofrap_common.py` — logique partagée (DB, bcrypt, Fernet, TOTP, QR). Contient `PASSWORD_LENGTH` et `SIX_MONTHS_SECONDS`.
- `functions/*/handler.py` — contrats d'entrée/sortie JSON (exemples ci-dessous).
- `frontend/app/main.py` — comment le frontend appelle les fonctions via `OPENFAAS_URL` / `OPENFAAS_GATEWAY`.
- `functions/stack.yml` — définition OpenFaaS (images, secrets, env).
- `deploy/bootstrap.sh` — script d'automatisation du déploiement Kubernetes/OpenFaaS.

Secrets & conventions
- OpenFaaS: les secrets sont montés en fichiers sous `/var/openfaas/secrets/<name>` (fonction `_read_secret()` dans `cofrap_common.py`).
- Noms de secrets documentés: `db-host`, `db-port`, `db-name`, `db-user`, `db-password`, `totp-encryption-key`.
- `cofrap_common.get_conn()` tombe en back‑up sur les variables d'environnement `DB_*` si les secrets ne sont pas présents — pratique pour tests locaux.
- TOTP: générer `pyotp.random_base32()`, chiffrer avec Fernet, stocker dans `users.mfa`. `authenticate` déchiffre et vérifie le code.

Contrats JSON (exemples)
- `generate-password` input: `{ "username": "alice" }` → 200 `{ "username": "alice", "password": "...", "qrcode": "<png base64>", "gendate": 1234567890 }`
- `generate-2fa` input: `{ "username": "alice" }` → 200 `{ "username": "alice", "qrcode": "<png base64 otpauth>", "gendate": 1234567890 }`
- `authenticate` input: `{ "username": "alice", "password": "...", "totp_code": "123456" }`
  - success: 200 `{ "authenticated": true, "expired": false }`
  - expired: 200 `{ "authenticated": false, "expired": true, "renew": true }`
  - invalid creds: 401 `{ "authenticated": false, "expired": false }`

Démarrage local (raccourci)

**⚠️ Prérequis ESSENTIELS avant de commencer**

1. **Installer Docker Desktop** (https://www.docker.com/products/docker-desktop)
   - Télécharge et installe Docker Desktop pour Windows.
   - Lance Docker Desktop (cherche l'icône Docker dans le menu Windows ou la barre des tâches).
   - Attends que le statut en bas à droite affiche "Docker is running" (cercle vert).
   - **Docker DOIT être actif avant de lancer les commandes `docker compose`**.

2. **Optionnel : activer Kubernetes dans Docker Desktop** (pour la procédure locale simple)
   - Settings > Kubernetes > Enable Kubernetes (redémarrage de Docker).
   - Cela permet seulement de tester un **cluster Kubernetes local Docker Desktop**.
   - C'est le cluster utilisé pour le déploiement local de ce projet.

3. **Installer Python 3.11+** (https://www.python.org/downloads/)
   - Télécharge et installe Python 3.11 ou plus récent.
   - Lors de l'installation, **coche "Add Python to PATH"**.

**Après ces étapes, tu peux procéder :**

1) Environnement Python & tests

```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
```

2) Démarrage rapide via Docker Compose (frontend + PostgreSQL)

Le dépôt contient un `docker-compose.yml` qui démarre le service `postgres` et le `frontend`. Cela permet de lancer l'UI, mais ATTENTION: le frontend appelle l'OpenFaaS Gateway pour exécuter les fonctions. Le `docker-compose.yml` fourni n'inclut pas OpenFaaS.

```powershell
docker compose up --build
# ensuite ouvrir http://localhost:8000
```

**Après avoir lancé `docker compose up --build` :**

1. Attends que les conteneurs se démarrent (tu verras des logs dans le terminal).
2. Ouvre un navigateur et va à **http://localhost:8000**.
3. Tu verras l'accueil du frontend COFRAP.
4. **Important** : les fonctions (create account, login) ne fonctionneront PAS car il n'y a pas d'OpenFaaS Gateway.
   - Le frontend affichera des erreurs si tu essaies de créer un compte (erreur de connexion au gateway).
5. Pour voir le frontend fonctionner complètement, tu as deux options :
   - **Option A (plus simple)** : déployer OpenFaaS localement via Docker Compose (voir section 4 si tu veux l'essayer).
   - **Option B (production-like)** : déployer sur Kubernetes Docker Desktop avec OpenFaaS (voir section 4, étapes 1-7).

**Pour arrêter les conteneurs :**
```powershell
# Ctrl+C dans le terminal où tourne docker compose, ou dans un autre terminal :
docker compose down
```

Remarque: pour que les appels depuis le frontend fonctionnent (création de compte, login), vous devez fournir une instance OpenFaaS + fonctions déployées ou pointer `OPENFAAS_URL` vers un gateway accessible.

3) Exécuter le frontend localement (UVicorn) et pointer vers un gateway existant

Si vous avez un gateway OpenFaaS disponible (local ou distant), exportez son URL avant de lancer le frontend.

```powershell
$Env:OPENFAAS_URL = 'http://gateway:8080'   # ou 'http://localhost:8080' selon votre setup
pip install -r frontend/requirements.txt
cd frontend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# ouvrir http://localhost:8000
```

4) Déployer OpenFaaS + fonctions sur Kubernetes Docker Desktop (production-like)

La stack technique utilisée ici : **Kubernetes Docker Desktop** + OpenFaaS (via Helm) + PostgreSQL.
Ce cluster local permet de déployer et tester toute la chaîne sur Windows sans serveur Linux séparé.

**Prérequis**
- Docker Desktop avec Kubernetes activé (Windows)
- Helm (https://helm.sh/docs/intro/install/)
- `faas-cli` (https://docs.openfaas.com/cli/install/)
- `kubectl` (fourni avec Kubernetes Docker Desktop)

**Étape 1 : Vérifier que Kubernetes Docker Desktop est actif**
```powershell
kubectl config current-context
kubectl get nodes
```

Le nœud doit apparaître comme `docker-desktop` en état `Ready`.

**Étape 2 : Créer PostgreSQL sur Kubernetes Docker Desktop (via kubectl apply)**

Le fichier `deploy/postgres/postgres.yaml` contient la définition complète de PostgreSQL (Deployment, Service, Secret, ConfigMap, PersistentVolumeClaim, etc.).

Ce fichier :
- Crée un namespace `cofrap`
- Crée un secret avec les identifiants DB (user: `cofrap`, password: `ChangeMe-Strong-Pwd`) — **remplace ce mot de passe par le tien après le déploiement initial**
- Crée la table `users` (colonne: `id, username, password, mfa, gendate, expired`)
- Lance un pod PostgreSQL 16 Alpine avec stockage persistant (2Gi)
- Expose le service PostgreSQL à `postgresql.cofrap.svc.cluster.local:5432`

**Commande pour déployer :**
```powershell
# depuis ta machine Windows avec kubectl configuré
kubectl apply -f deploy/postgres/postgres.yaml

# vérifier que le pod est en cours d'exécution
kubectl get pods -n cofrap
# attendre quelques secondes (STATUS = Running)

# vérifier le service
kubectl get svc -n cofrap
# postgresql doit être accessible à postgresql.cofrap.svc.cluster.local:5432
```

**Pour modifier le mot de passe DB :**
- Édite `deploy/postgres/postgres.yaml`, remplace la valeur `ChangeMe-Strong-Pwd` dans le secret.
- Relance : `kubectl apply -f deploy/postgres/postgres.yaml`
- Supprime le pod pour forcer redémarrage : `kubectl delete pod -l app=postgresql -n cofrap`

**Étape 3 : Installer OpenFaaS via Helm**
```powershell
# ajouter repo Helm OpenFaaS
helm repo add openfaas https://openfaas.github.io/faas-netes/
helm repo update

# créer namespace et installer OpenFaaS
kubectl apply -f https://raw.githubusercontent.com/openfaas/faas-netes/master/namespaces.yml
helm upgrade --install openfaas openfaas/openfaas -n openfaas `
  --set functionNamespace=openfaas-fn `
  --set generateBasicAuth=true
```

**Étape 4 : Accéder au gateway OpenFaaS (port-forward depuis ta machine)**
```powershell
# dans un terminal PowerShell séparé (reste actif) :
kubectl port-forward -n openfaas svc/gateway 8080:8080

# gateway accessible à: http://localhost:8080 (depuis ta machine)
```

**Étape 5 : Créer les secrets OpenFaaS (pour les fonctions)**

Les fonctions OpenFaaS ont besoin des 6 secrets suivants pour se connecter à PostgreSQL et chiffrer les secrets TOTP.

**Important :** l'adresse PostgreSQL depuis les fonctions OpenFaaS est `postgresql.cofrap.svc.cluster.local:5432` (DNS interne Kubernetes).

```powershell
# récupérer le mot de passe basic-auth d'OpenFaaS
$basicAuthPassword = kubectl get secret -n openfaas basic-auth -o jsonpath="{.data.basic-auth-password}" | ConvertFrom-Base64String

# login faas-cli
faas-cli login --password $basicAuthPassword --gateway http://localhost:8080

# générer une clé Fernet (pour chiffrer les secrets TOTP)
$fernetKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Write-Host "Clé Fernet générée: $fernetKey"

# créer les 6 secrets OpenFaaS (remplace <MDP_DB> par le mot de passe PostgreSQL que tu as mis dans l'étape 3)
faas-cli secret create db-host --from-literal "postgresql.cofrap.svc.cluster.local" -n openfaas-fn --gateway http://localhost:8080
faas-cli secret create db-port --from-literal "5432" -n openfaas-fn --gateway http://localhost:8080
faas-cli secret create db-name --from-literal "cofrap" -n openfaas-fn --gateway http://localhost:8080
faas-cli secret create db-user --from-literal "cofrap" -n openfaas-fn --gateway http://localhost:8080
faas-cli secret create db-password --from-literal "<MDP_DB>" -n openfaas-fn --gateway http://localhost:8080
faas-cli secret create totp-encryption-key --from-literal "$fernetKey" -n openfaas-fn --gateway http://localhost:8080

# vérifier les secrets créés
kubectl get secrets -n openfaas-fn
```

**Étape 6 : Déployer les fonctions**
```powershell
cd functions
faas-cli up -f stack.yml --gateway http://localhost:8080
```

**Étape 7 : Lancer le frontend (vers le gateway OpenFaaS)**
```powershell
$Env:OPENFAAS_URL = 'http://localhost:8080'
# voir section 3 ci-dessus pour lancer le frontend
```

**Script d'automatisation**
Ce dépôt fournit `deploy/bootstrap.sh` pour automatiser une partie du déploiement ; adapte-le selon ton infrastructure locale.

Bonnes pratiques pour les modifications
- Garder les contrats JSON stables entre fonctions et le frontend.
- Les modifications de secret handling, de la table `users` ou des constantes cryptographiques (TTL, algorithmes) requièrent revue humaine.
- Refactorings sûrs: organiser/utiliser davantage `functions/common/cofrap_common.py`, corriger/ajouter des tests dans `tests/`.

Si vous voulez, je peux:
- Lancer la suite de tests ici et vous donner le résultat.
- Mettre à jour le README avec des captures d'exemples (exemples de payloads) ou ajouter un guide pas-à-pas pour déployer OpenFaaS localement.

```