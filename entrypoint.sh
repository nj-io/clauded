#!/bin/bash
# Shadow macOS miniconda/anaconda python with Linux python for git hooks
# (macOS python binaries mounted via bind mount can't execute on Linux)
for conda_dir in "$HOME/dev/miniconda3" "$HOME/dev/anaconda3" "$HOME/miniconda3" "$HOME/anaconda3"; do
    conda_python="$conda_dir/bin/python"
    if [ -f "$conda_python" ] && ! "$conda_python" --version >/dev/null 2>&1; then
        sudo mount --bind /usr/bin/python3 "$conda_python" 2>/dev/null || true
    fi
done

# Voice mode: run a container-local PulseAudio whose default source is a
# pipe-source fed (on demand) from the Mac mic by mic-bridge-client.py.
# Claude Code's `sox -d` then records through it. Gated on CLAUDED_VOICE=1.
setup_voice() {
    # Keep the PulseAudio runtime dir and the mic FIFO on a container-local
    # tmpfs (/dev/shm), NOT under /tmp — clauded bind-mounts /tmp from the Mac,
    # and named pipes / Unix sockets on Docker Desktop's file sharing are unreliable.
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/dev/shm/clauded-xdg}"
    mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"
    export CLAUDED_MIC_FIFO="${CLAUDED_MIC_FIFO:-/dev/shm/clauded-mic.fifo}"
    pulseaudio --start --exit-idle-time=-1 >/dev/null 2>&1 || return 0
    for _ in $(seq 1 20); do pactl info >/dev/null 2>&1 && break; sleep 0.1; done
    pactl info >/dev/null 2>&1 || return 0
    pactl load-module module-pipe-source source_name=micbridge \
        file="$CLAUDED_MIC_FIFO" format=s16le rate=16000 channels=1 >/dev/null 2>&1 || true
    pactl set-default-source micbridge >/dev/null 2>&1 || true
    export AUDIODRIVER=pulseaudio
    nohup python3 /usr/local/bin/mic-bridge-client.py >/dev/null 2>&1 &
}
if [ "${CLAUDED_VOICE:-}" = "1" ]; then
    setup_voice || true
fi

exec claude "$@"
