@echo off
wsl -d Ubuntu bash -c "/home/ai/.nvm/versions/node/v20.19.3/bin/node /home/ai/.nvm/versions/node/v20.19.3/bin/claude --dangerously-skip-permissions %*"
