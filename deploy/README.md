# Déploiement COFRAP sur Kubernetes Docker Desktop

## Prérequis
- Docker Desktop avec Kubernetes activé, `kubectl`, `helm`, `faas-cli`, Docker.
- Registre OCI (GHCR/Docker Hub) pour pousser les images.

## 1. OpenFaaS
```bash
helm repo add openfaas https://openfaas.github.io/faas-netes/ && helm repo update
kubectl apply -f https://raw.githubusercontent.com/openfaas/faas-netes/master/namespaces.yml
helm upgrade --install openfaas openfaas/openfaas -n openfaas \
  --set functionNamespace=openfaas-fn --set generateBasicAuth=true
kubectl port-forward -n openfaas svc/gateway 8080:8080 &
faas-cli login --password $(kubectl get secret -n openfaas basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 -d)
```

## 2. PostgreSQL
```bash
kubectl apply -f deploy/postgres/postgres.yaml
```

## 3. Secrets (connexion DB découpée + clé TOTP)
```bash
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"  # clé
faas-cli secret create db-host     --from-literal "postgresql.cofrap.svc.cluster.local" -n openfaas-fn
faas-cli secret create db-port     --from-literal "5432"   -n openfaas-fn
faas-cli secret create db-name     --from-literal "cofrap" -n openfaas-fn
faas-cli secret create db-user     --from-literal "cofrap" -n openfaas-fn
faas-cli secret create db-password --from-literal "<MDP_DB>" -n openfaas-fn
faas-cli secret create totp-encryption-key --from-literal "<CLE_FERNET>" -n openfaas-fn
```

## 4. Fonctions
```bash
cd functions && faas-cli up -f stack.yml   # build + push + deploy
```

## 5. Frontend
```bash
kubectl apply -f deploy/frontend/frontend.yaml   # Ingress http://cofrap.local
```

Tout-en-un : `bash deploy/bootstrap.sh` (à adapter au contexte Windows/Docker Desktop si nécessaire).
