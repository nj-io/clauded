#!/bin/bash
# Shadow macOS miniconda/anaconda python with Linux python for git hooks
# (macOS python binaries mounted via bind mount can't execute on Linux)
for conda_dir in "$HOME/dev/miniconda3" "$HOME/dev/anaconda3" "$HOME/miniconda3" "$HOME/anaconda3"; do
    conda_python="$conda_dir/bin/python"
    if [ -f "$conda_python" ] && ! "$conda_python" --version >/dev/null 2>&1; then
        sudo mount --bind /usr/bin/python3 "$conda_python" 2>/dev/null || true
    fi
done

exec claude "$@"
