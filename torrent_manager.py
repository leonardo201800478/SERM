import subprocess
import time
from pathlib import Path

try:
    from qbittorrentapi import Client, LoginFailed
    QB_AVAILABLE = True
except ImportError:
    QB_AVAILABLE = False
    print("qbittorrent-api não instalado. Instale com: pip install qbittorrent-api")

def start_qbittorrent(qb_exe_path):
    if qb_exe_path and Path(qb_exe_path).exists():
        subprocess.Popen([qb_exe_path], shell=True)
        time.sleep(3)
        return True
    return False

def connect_qbittorrent(host="localhost", port=8080, username="admin", password="adminadmin"):
    if not QB_AVAILABLE:
        return None
    client = Client(host=host, port=port, username=username, password=password)
    try:
        client.auth_log_in()
        return client
    except LoginFailed:
        return None

def add_torrent_with_files(client, magnet_link, files_to_select, save_path):
    if not client or not magnet_link:
        return False
    try:
        result = client.torrents_add(
            urls=magnet_link,
            save_path=str(save_path),
            paused=True
        )
        if result != "Ok.":
            return False
        torrents = client.torrents_info()
        if not torrents:
            return False
        latest = torrents[0]
        files_info = client.torrents_files(latest.hash)
        selected_indices = []
        for f in files_info:
            base = Path(f.name).stem
            if base in files_to_select:
                selected_indices.append(f.index)
        if selected_indices:
            priorities = [0] * len(files_info)
            for idx in selected_indices:
                priorities[idx] = 1
            client.torrents_set_priority(latest.hash, priorities)
            client.torrents_resume([latest.hash])
        else:
            client.torrents_resume([latest.hash])
        return True
    except Exception as e:
        print(f"Erro ao adicionar torrent: {e}")
        return False