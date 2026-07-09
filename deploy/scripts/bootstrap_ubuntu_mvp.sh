#!/usr/bin/env bash
set -euo pipefail

echo "This is a reference bootstrap script for Ubuntu 22.04 MVP deployment."
echo "Review every command before running it on a real server."
echo "No secrets, IPs, or tokens should be placed in this script."

sudo apt update
sudo apt install -y \
  git \
  curl \
  wget \
  rsync \
  nginx \
  python3.11 \
  python3.11-venv \
  python3-pip \
  build-essential \
  unzip \
  htop \
  docker.io

echo "Create the quant user manually if it does not exist:"
echo "  sudo adduser quant"
echo "  sudo usermod -aG sudo quant"
echo "  sudo usermod -aG docker quant"
echo "Log out and back in after changing group membership."
