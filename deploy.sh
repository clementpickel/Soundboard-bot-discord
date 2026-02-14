#!/usr/bin/env bash
set -euo pipefail

# === CONFIG (override on command-line: SERVER=... USER=... ./deploy.sh) ===
SERVER="${SERVER:-100.119.201.30}"
USER="${USER:-ubuntu}"
LOCAL_DIR="."                        # current directory (project root)
IMAGE_NAME="soundboard-bot"          # docker image name (local tag)
CONTAINER_NAME="soundboard-bot-container"
PORT="5000"                          # host port to publish (web interface)
REMOTE_PORT="5000"                   # container port exposed by the image
REMOTE_SUDO="${REMOTE_SUDO:-}"       # set to "sudo" if remote docker requires sudo
SSH_OPTS="${SSH_OPTS:-}"             # optional extra ssh options
REMOTE_DATA_DIR="${REMOTE_DATA_DIR:-~/soundboard-bot}" # remote directory for persistent data (uses home dir)

# tar filename with timestamp to avoid collisions
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARFILE="${IMAGE_NAME}_${TIMESTAMP}.tar"

echo "==> Deploying ${IMAGE_NAME} to ${USER}@${SERVER}"

# === 0. Pre-checks
if [ ! -f "bot.py" ]; then
  echo "ERROR: bot.py not found. Run this script from the project root."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "ERROR: .env file not found. Please create it with your DISCORD_TOKEN."
  exit 1
fi

# === 1. Build Docker image locally
echo "🔧 Building Docker image (${IMAGE_NAME})..."
docker build -t "${IMAGE_NAME}" .

# === 2. Save image as tar file (local)
echo "📦 Saving Docker image to ${TARFILE}..."
docker save -o "${TARFILE}" "${IMAGE_NAME}"

# ensure local tar is removed on exit
_cleanup_local() {
  rm -f "${TARFILE}" || true
}
trap _cleanup_local EXIT

# === 3. Copy image and required files to remote server
echo "📤 Copying image to ${USER}@${SERVER}:~/"
scp ${SSH_OPTS} "${TARFILE}" "${USER}@${SERVER}:~/"

echo "📤 Copying .env file to ${USER}@${SERVER}:~/"
scp ${SSH_OPTS} ".env" "${USER}@${SERVER}:~/.env.soundboard"

echo "📤 Copying sounds.json to ${USER}@${SERVER}:~/"
scp ${SSH_OPTS} "sounds.json" "${USER}@${SERVER}:~/sounds.json.soundboard"

# === 4. Connect via SSH and run container on remote
echo "🚀 Deploying container on remote server (${SERVER})..."
ssh ${SSH_OPTS} "${USER}@${SERVER}" bash -e <<EOF
set -euo pipefail

TARFILE_REMOTE="\$(basename "${TARFILE}")"
IMAGE_NAME="${IMAGE_NAME}"
CONTAINER_NAME="${CONTAINER_NAME}"
PORT="${PORT}"
REMOTE_PORT="${REMOTE_PORT}"
REMOTE_SUDO="${REMOTE_SUDO:-}"
REMOTE_DATA_DIR="${REMOTE_DATA_DIR}"

# Expand ~ to absolute path if present
REMOTE_DATA_DIR="\${REMOTE_DATA_DIR/#\~\//\$HOME/}"
REMOTE_DATA_DIR="\${REMOTE_DATA_DIR/#\~/\$HOME}"

echo "-> Using data directory: \${REMOTE_DATA_DIR}"
echo "-> Creating remote data directory at \${REMOTE_DATA_DIR}..."
mkdir -p "\${REMOTE_DATA_DIR}/assets"

echo "-> Moving .env and sounds.json to data directory..."
mv ~/.env.soundboard "\${REMOTE_DATA_DIR}/.env"
mv ~/sounds.json.soundboard "\${REMOTE_DATA_DIR}/sounds.json"

echo "-> Loading image from \${TARFILE_REMOTE}..."
\${REMOTE_SUDO} docker load -i "\${TARFILE_REMOTE}"

echo "-> Stopping existing container (if any)..."
\${REMOTE_SUDO} docker stop "\${CONTAINER_NAME}" >/dev/null 2>&1 || true
echo "-> Removing existing container (if any)..."
\${REMOTE_SUDO} docker rm "\${CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "-> Running new container..."
\${REMOTE_SUDO} docker run -d \\
  -p \${PORT}:\${REMOTE_PORT} \\
  -v "\${REMOTE_DATA_DIR}/assets:/app/assets" \\
  -v "\${REMOTE_DATA_DIR}/sounds.json:/app/sounds.json" \\
  -v "\${REMOTE_DATA_DIR}/.env:/app/.env:ro" \\
  --restart unless-stopped \\
  --name "\${CONTAINER_NAME}" \\
  "\${IMAGE_NAME}"

echo "-> Removing remote tarfile..."
rm -f "\${TARFILE_REMOTE}" || true

echo "✅ Remote deployment finished."
echo "   Container: \${CONTAINER_NAME}"
echo "   Web Interface: http://${SERVER}:\${PORT}"
echo "   Data Directory: \${REMOTE_DATA_DIR}"
EOF

echo ""
echo "✅ Deployment complete!"
echo "   Access web interface at: http://${SERVER}:${PORT}"
echo "   View logs with: ssh ${USER}@${SERVER} '${REMOTE_SUDO} docker logs -f ${CONTAINER_NAME}'"
