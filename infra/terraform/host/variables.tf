# infra/terraform/host/variables.tf — IAC-01: input variables for k3s bare-metal install
#
# Secret-shaped variables (ssh_host, ssh_user, ssh_private_key_path) intentionally
# have NO default — operators must supply them via terraform.tfvars (never committed).

variable "ssh_host" {
  type        = string
  description = "IP address or hostname of the bare-metal node to provision with k3s."
}

variable "ssh_user" {
  type        = string
  description = "SSH username on the target node (must have sudo privileges for the k3s install script)."
}

variable "ssh_private_key_path" {
  type        = string
  description = "Path to the SSH private key file on the operator's machine (e.g. ~/.ssh/clubcore_node). Never commit the actual key."
}

variable "k3s_version" {
  type        = string
  description = "k3s release tag to install (e.g. 'v1.32.5+k3s1'). Pin to an explicit version for reproducibility. Must match the CNPG manifest version tested in k3d (Phase 118 SUMMARY)."
  default     = "v1.32.5+k3s1"
}

variable "k3s_channel" {
  type        = string
  description = "k3s release channel ('stable' | 'latest' | 'v1.32'). Used when INSTALL_K3S_VERSION is empty; ignored when k3s_version is set."
  default     = "stable"
}
