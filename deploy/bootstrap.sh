#!/usr/bin/env bash
# Bootstrap COFRAP sur un cluster K3S : OpenFaaS + PostgreSQL + secrets.
set -euo pipefail

NS_FAAS=openfaas
NS_COFRAP=cofrap

echo "==> Installation OpenFaaS (Helm)"
helm repo add openfaas https://openfaas.github.io/faas-netes/ >/dev/null
helm repo update >/dev/null
kubectl create namespace $NS_FAAS --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace ${NS_FAAS}-fn --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install openfaas openfaas/openfaas \
  --namespace $NS_FAAS --set functionNamespace=${NS_FAAS}-fn --set generateBasicAuth=true

echo "==> PostgreSQL (Helm)"
helm upgrade --install cofrap-postgres deploy/helm/cofrap-postgres -n $NS_COFRAP --create-namespace

echo "==> Secrets fonctions (DB découpés + clé TOTP)"
FERNET=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
faas-cli secret create db-host     --from-literal "postgresql.cofrap.svc.cluster.local" -n ${NS_FAAS}-fn || true
faas-cli secret create db-port     --from-literal "5432"        -n ${NS_FAAS}-fn || true
faas-cli secret create db-name     --from-literal "cofrap"      -n ${NS_FAAS}-fn || true
faas-cli secret create db-user     --from-literal "cofrap"      -n ${NS_FAAS}-fn || true
faas-cli secret create db-password --from-literal "ChangeMe-Strong-Pwd" -n ${NS_FAAS}-fn || true
faas-cli secret create totp-encryption-key --from-literal "$FERNET" -n ${NS_FAAS}-fn || true

echo "==> Build & deploy fonctions"
cd functions && faas-cli up -f stack.yml && cd ..

echo "==> Frontend"
kubectl apply -f deploy/frontend/frontend.yaml

echo "OK. URL gateway : http://127.0.0.1:8080 (port-forward) ; frontend : http://cofrap.local"
