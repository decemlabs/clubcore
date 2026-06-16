# Sealed Secrets Controller RSA Key Backup Runbook

**Requirement:** SEC-02 (pitfall P6)
**Risk level:** CRITICAL — controller key loss on cluster rebuild = ALL SealedSecrets permanently unrecoverable

---

## Why This Matters (P6)

The sealed-secrets controller maintains a single RSA key pair stored as a Kubernetes Secret
in the `kube-system` namespace. Every `SealedSecret` in the cluster is RSA-encrypted
**specifically against this key**. If the cluster is destroyed (reinstalled, reset, or
migrated) and the controller key Secret is not restored beforehand, the controller generates
a new RSA key on startup — and **none of the previously sealed Secrets can be decrypted**.

This is not a recoverable situation. There is no fallback, no backup decryption path, no
way to retrieve the plaintext values from an encrypted SealedSecret without the original RSA key.

**For this project:** There is no git remote. Backup is a second PC (same building, different
machine). The RSA key MUST be present on that second PC alongside the repo copy.

> OPERATOR-PENDING: The export command below and the off-node copy require a live k3d cluster
> with the sealed-secrets controller installed. This step cannot be performed in the build
> sandbox. It MUST be completed by the operator before any production deploy.

---

## P6 Hard Gate — Acceptance Criteria

This gate MUST be closed before any live/production deploy:

- [ ] Controller RSA key exported from the cluster
- [ ] Exported key file copied to the **second PC** (off-node)
- [ ] Restore verification completed (see Step 5 below)
- [ ] Key file deleted from the source machine (or stored in a protected location)

Do NOT mark SEC-02 as complete until all four checkboxes are ticked.

---

## Step 1 — Install sealed-secrets v0.37.0

```bash
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm repo update
helm install sealed-secrets \
  -n kube-system \
  --create-namespace \
  --version 0.37.0 \
  sealed-secrets/sealed-secrets

# Verify the controller is Running
kubectl get pod -n kube-system -l app.kubernetes.io/name=sealed-secrets
# Expected: sealed-secrets-<hash>   Running   1/1
```

---

## Step 2 — Export the RSA Private Key

Run this command **immediately after installing the controller**, before sealing any secrets:

```bash
# Export the controller RSA key Secret from kube-system
# The label sealedsecrets.bitnami.com/sealed-secrets-key selects the key Secret(s).
kubectl get secret \
  -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml \
  > /tmp/clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml

# Verify the file is non-empty and contains the expected Secret kind
head -5 /tmp/clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml
# Expected output:
#   apiVersion: v1
#   items:
#   - apiVersion: v1
#     data:
#       tls.crt: <base64>

echo "Exported key file: /tmp/clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml"
```

**Alternatively**, use the helper script which exports the key as part of the seal workflow:

```bash
bash infra/scripts/seal-secrets.sh
```

The script prints the export path at the end and refuses to write the key inside the repo.

---

## Step 3 — Copy the Key to the Second PC (OPERATOR-PENDING)

> This step is manual. There is no git remote. Use scp, a USB drive, or a direct network
> copy to transfer the key file to the second PC.

```bash
# Option A: scp to the second PC (replace <second-pc-ip> and <user>)
scp /tmp/clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml \
    <user>@<second-pc-ip>:/home/<user>/clubcore-backups/

# Option B: Mount a USB drive and copy
cp /tmp/clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml \
    /Volumes/<usb-drive>/clubcore-backups/

# After copying, delete the file from /tmp (do not leave it on a single machine)
rm /tmp/clubcore-sealed-secrets-key-$(date +%Y%m%d).yaml
```

**Where to store it on the second PC:**
- Recommended: alongside the repo copy, in a `clubcore-backups/` sibling directory
- Keep it in a protected directory (not world-readable): `chmod 600 <keyfile>`
- Consider also printing a QR code or storing in a hardware-encrypted USB (defense in depth)

---

## Step 4 — Restore Procedure (On Cluster Rebuild)

If the cluster is destroyed or reinstalled, restore the controller key **BEFORE** installing
the sealed-secrets controller. If you install the controller first, it generates a new key
and the restore window closes.

```bash
# 1. Apply the backed-up key Secret BEFORE installing the controller
kubectl apply -f /path/to/clubcore-sealed-secrets-key-<date>.yaml

# Verify the key Secret is present in kube-system
kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key
# Expected: one or more Secrets listed

# 2. Install the sealed-secrets controller (it will find and use the existing key)
helm install sealed-secrets \
  -n kube-system \
  --create-namespace \
  --version 0.37.0 \
  sealed-secrets/sealed-secrets

# 3. Verify the controller started and uses the existing key (NOT a new one)
kubectl logs -n kube-system -l app.kubernetes.io/name=sealed-secrets | tail -20
# Look for: "found existing key" or "loaded key" — NOT "generating new key"
```

**Order matters:** Key restore MUST precede controller install on rebuild.

---

## Step 5 — Restore Verification (Required Before Closing P6 Gate)

After restoring the key on a fresh cluster, verify the controller can unseal an existing
SealedSecret. This confirms the restore worked before any production deploy.

```bash
# 1. Seal a test value against the current controller cert
echo -n "test-value-$(date +%s)" | \
  kubeseal --raw \
  --namespace default \
  --name clubcore-restore-test \
  --controller-name sealed-secrets \
  --controller-namespace kube-system \
  --from-file /dev/stdin

# 2. Create a minimal SealedSecret with the encrypted test value
# (Use the encryptedData output from the command above)

# 3. Apply the SealedSecret to the cluster
kubectl apply -f /tmp/restore-test.yaml

# 4. Wait for the controller to unseal it
kubectl wait secret/clubcore-restore-test --for=condition=Ready --timeout=30s 2>/dev/null \
  || kubectl get secret clubcore-restore-test 2>/dev/null

# 5. Confirm the Secret exists and decodes correctly
kubectl get secret clubcore-restore-test -o jsonpath='{.data.stdin}' | base64 -d
# Expected: the test-value string from step 1

# 6. Clean up
kubectl delete secret clubcore-restore-test
```

If the controller can unseal the test SealedSecret, the RSA key restore succeeded.

---

## Step 6 — Seal the App Secret

After verifying the key backup and restore:

```bash
# Set the plaintext env vars (do NOT commit these to any file)
export SEAL_SECRET_KEY="$(openssl rand -hex 32)"
export SEAL_DATABASE_URL="postgresql+asyncpg://app:<password>@clubcore-postgres-rw:5432/clubcore"
export SEAL_S3_ACCESS_KEY_ID="your-s3-access-key"
export SEAL_S3_SECRET_ACCESS_KEY="your-s3-secret-key"
export SEAL_TELEGRAM_BOT_TOKEN="your-bot-father-token"
# Optional email credentials
# export SEAL_EMAIL_AWS_ACCESS_KEY_ID="..."
# export SEAL_EMAIL_AWS_SECRET_ACCESS_KEY="..."
# export SEAL_EMAIL_WEBHOOK_SECRET="..."

# Run the sealing script
bash infra/scripts/seal-secrets.sh

# Copy the encryptedData output into a values-production.yaml (NOT values.yaml)
# Deploy with:
helm upgrade --install clubcore infra/helm/clubcore \
  --set secrets.plaintextForLocalK3d=false \
  --set secrets.sealed.enabled=true \
  -f /path/to/values-production.yaml
```

---

## Security Notes

| Item | Requirement |
|------|------------|
| RSA key file permissions | `chmod 600 <keyfile>` — only the owner should read it |
| RSA key location | Outside the git repo, on the second PC alongside the repo copy |
| Plaintext values | NEVER committed to git, NEVER in values.yaml (only env vars during sealing) |
| Controller version | Pin to v0.37.0 — use the same version on restore to avoid format drift |
| Key rotation | Re-seal all SealedSecrets after rotating the controller key |

---

## Quick Reference — Key Commands

```bash
# Export key
kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > key.yaml

# Restore key (before controller install)
kubectl apply -f key.yaml

# Fetch controller cert (public — safe to commit)
kubeseal --fetch-cert --controller-name sealed-secrets --controller-namespace kube-system

# Seal a file
kubeseal --format yaml --namespace default --name clubcore-app-secret < plaintext-secret.yaml > sealed.yaml

# Run the full seal workflow (this script)
bash infra/scripts/seal-secrets.sh
```
