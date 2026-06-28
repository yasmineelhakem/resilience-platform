# Infrastructure and Argo CD Deployment Guide

## 1. Azure Login

Authenticate to Azure:

```bash
az login
```

## 2. Create Terraform Backend Storage

Create the resource group for Terraform state:

```bash
az group create --name rg-astro-backend --location francecentral
```

Create the storage account for Terraform state:

```bash
az storage account create \
  --name astrotfstate \
  --resource-group rg-astro-backend \
  --location francecentral \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access false \
  --min-tls-version TLS1_2
```

Create the blob container:

```bash
az storage container create \
  --name tfstate \
  --account-name sttfstateresiliencepfe \
  --auth-mode login
```

Get the current subscription ID:

```bash
az account show --query id --output tsv
```

Set the subscription ID environment variable:

```bash
export ARM_SUBSCRIPTION_ID="<subscription-id>"
```

## 3. Provision Infrastructure with Terraform

Run Terraform from the `terraform/` directory to provision the infrastructure:

```bash
cd terraform
terraform init
terraform apply
```

## 4. Connect to the AKS Cluster

Get AKS credentials:

```bash
az aks get-credentials \
  --resource-group rg-astro \
  --name astro-aks1
```

Verify the cluster nodes:

```bash
kubectl get nodes
```

## 5. Install Argo CD

Add the Argo Helm repository and update local charts:

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
```

Install Argo CD into the `argocd` namespace using the bootstrap values:

```bash
helm install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --values bootstrap/argocd-values.yaml \
  --wait
```

Check Argo CD pods:

```bash
kubectl get pods -n argocd -o wide
```

Expose the Argo CD server as a LoadBalancer:

```bash
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'
```

Get the Argo CD server IP address:

```bash
kubectl get svc argocd-server -n argocd -o=jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Login to Argo CD:

```bash
argocd login <ARGOCD_SERVER_IP> --username admin --insecure
```

Get the initial admin password:

```bash
argocd admin initial-password -n argocd
```

## 6. Connect GitHub to Argo CD

Store your GitHub personal access token in Azure Key Vault:

```bash
az keyvault secret set \
  --vault-name astro-kv \
  --name github-pat \
  --value "<your-github-PAT>"
```

Verify the secret is stored:

```bash
az keyvault secret list --vault-name astro-kv --output table
```

Add the GitHub repository to Argo CD using the secret value:

```bash
argocd repo add https://github.com/yasmineelhakem/resilience-platform.git \
  --username yasmineelhakem \
  --password $(az keyvault secret show \
      --vault-name astro-kv \
      --name github-pat \
      --query value \
      --output tsv)
```

Verify the repo is added:

```bash
argocd repo list
```

## 7. Deploy the App of Apps

Apply the bootstrap parent application manifest:

```bash
kubectl apply -f bootstrap/parent-app.yaml
```

Check the Argo CD application list:

```bash
argocd app list
```
