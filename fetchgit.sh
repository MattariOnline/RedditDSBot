#/bin/sh

# Fetch git, reset local to fetched git, and chmod all files in directory
git fetch --all
git reset --hard origin/master
chmod 755 *
