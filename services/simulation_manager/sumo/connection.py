"""SUMO connection management.

Encapsulates the difference between local-spawn mode (Manager launches
SUMO as a subprocess and connects via stdin TCP) and remote-connect mode
(SUMO is already running on the host; Manager connects to its TraCI port).

Used by SimulationController so the rest of the codebase doesn't need to
care which mode is active.

Modes:
  SUMO_MODE=local  — current default for non-Docker dev. Manager spawns
                     sumo or sumo-gui as a subprocess (requires SUMO_HOME).
  SUMO_MODE=remote — Docker default. Manager connects to an externally-
                     running SUMO via host.docker.internal:8813.
"""
from __future__ import annotations
import os
import sys

import traci

from config import config


def open_sumo_connection(*, config_file: str, use_gui: bool, suppress_demand: bool = False) -> dict:
    """Open a TraCI connection to SUMO in the configured mode.

    Returns a dict describing the connection (mode, host/port or binary).
    """
    mode = config.SUMO_MODE
    if mode == 'remote':
        return _connect_remote()
    return _start_local(config_file=config_file, use_gui=use_gui, suppress_demand=suppress_demand)


def close_sumo_connection() -> None:
    """Close the active TraCI connection.

    In local mode this terminates the spawned subprocess. In remote mode
    it just disconnects the TCP socket; the SUMO process keeps running
    on the host.
    """
    try:
        traci.close()
    except Exception as exc:
        print(f"[SUMO] Error during traci.close(): {exc}")


def ensure_sumo_home_on_path() -> None:
    """Add $SUMO_HOME/tools to sys.path if SUMO_HOME is set.

    Required for sumolib (used to parse .net.xml files even in remote mode).
    Does not raise if SUMO_HOME is missing — sumolib may also be available
    via pip install in the container.
    """
    sumo_home = os.environ.get('SUMO_HOME')
    if sumo_home:
        tools = os.path.join(sumo_home, 'tools')
        if tools not in sys.path:
            sys.path.append(tools)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _start_local(*, config_file: str, use_gui: bool, suppress_demand: bool) -> dict:
    """Spawn sumo/sumo-gui as a subprocess and connect via TraCI."""
    if 'SUMO_HOME' not in os.environ:
        raise RuntimeError(
            "SUMO_HOME environment variable is not set. "
            "Cannot launch local SUMO. Either set SUMO_HOME, or run with SUMO_MODE=remote."
        )

    sumo_binary = 'sumo-gui' if use_gui else 'sumo'
    sumo_cmd = [sumo_binary, '-c', config_file, '--start']

    if suppress_demand:
        sumo_cmd += ['--scale', '0']
        print('[SUMO] Built-in demand suppressed (--scale 0).')

    print(f"[SUMO] Local mode — launching: {' '.join(sumo_cmd)}")
    traci.start(sumo_cmd)
    return {
        'mode': 'local',
        'binary': sumo_binary,
        'config_file': config_file,
    }


def _connect_remote() -> dict:
    """Connect to an externally-launched SUMO instance.

    The user (or a host-side launcher) must have already started SUMO with:
        sumo-gui -c <scenario>.sumo.cfg --remote-port 8813 --start

    Inside Docker, the host is reachable via `host.docker.internal` on
    Windows/Mac. On Linux Docker, set SUMO_HOST appropriately or use the
    `extra_hosts: ["host.docker.internal:host-gateway"]` compose entry.
    """
    host = config.SUMO_HOST
    port = config.SUMO_PORT
    print(f"[SUMO] Remote mode — connecting to {host}:{port}")
    traci.init(port=port, host=host)
    return {
        'mode': 'remote',
        'host': host,
        'port': port,
    }
