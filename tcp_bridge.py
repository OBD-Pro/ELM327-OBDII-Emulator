"""Serve the emulator over TCP, like a Wi-Fi ELM327 adapter (default port 35000).

The emulator runs on a pseudo-terminal; one TCP client at a time is relayed to it. Apps connect to
<this computer's IP>:35000 using their Wi-Fi adapter option.

    python tcp_bridge.py --port 35000 -- -s idle -v
"""
import argparse
import os
import pty
import select
import signal
import socket
import subprocess
import sys
import tty


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=35000)
    parser.add_argument("emulator_args", nargs="*", help="passed to obd_emulator.py (after --)")
    args = parser.parse_args()

    master, slave = pty.openpty()
    tty.setraw(slave)
    os.set_blocking(master, False)
    here = os.path.dirname(os.path.abspath(__file__))
    emu = subprocess.Popen([sys.executable, os.path.join(here, "obd_emulator.py"), "-p", os.ttyname(slave),
                            *args.emulator_args])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(1)
    print(f"ELM327 emulator on tcp://{args.host}:{args.port} (Wi-Fi adapter mode)", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    client = None
    try:
        while emu.poll() is None:
            watch = [server, master] + ([client] if client else [])
            for ready in select.select(watch, [], [], 0.2)[0]:
                if ready is server:
                    conn, addr = server.accept()
                    if client:
                        client.close()  # newest client wins, like a dongle after a reconnect
                    client = conn
                    client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    print(f"client connected: {addr[0]}:{addr[1]}", flush=True)
                elif ready is master:
                    try:
                        data = os.read(master, 4096)
                    except (BlockingIOError, OSError):
                        continue
                    if client:
                        try:
                            client.sendall(data)
                        except OSError:
                            client.close()
                            client = None
                else:
                    data = client.recv(4096)
                    if not data:
                        print("client disconnected", flush=True)
                        client.close()
                        client = None
                        continue
                    os.write(master, data)
    except KeyboardInterrupt:
        pass
    finally:
        emu.terminate()
        server.close()


if __name__ == "__main__":
    main()
