import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent


class FakeContainer:
    def __init__(self, name, labels):
        self.name = name
        self.labels = labels
        self.status = "running"
        self.stop_calls = 0
        self.start_calls = 0

    def stop(self, timeout=30):
        self.stop_calls += 1
        self.status = "exited"

    def start(self):
        self.start_calls += 1
        self.status = "running"


class FakeVolume:
    def __init__(self, name, mountpoint, labels):
        self.name = name
        self.attrs = {"Mountpoint": str(mountpoint), "Labels": labels}


class FakeVolumes:
    def __init__(self, volumes):
        self._volumes = volumes

    def list(self):
        return self._volumes


class FakeContainers:
    def __init__(self, containers):
        self._containers = containers

    def list(self, all=False):
        return self._containers


class FakeDocker:
    def __init__(self, volumes, containers):
        self.volumes = FakeVolumes(volumes)
        self.containers = FakeContainers(containers)


def test_server_backup_contains_database_volumes_and_restore_is_transactional(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)

    game = tmp_path / "game-data"
    database = tmp_path / "database-data"
    game.mkdir()
    database.mkdir()
    (game / "server.properties").write_text("motd=before")
    (database / "PG_VERSION").write_text("16")
    (database / "base-data").write_text("database-before")

    db_container = FakeContainer("lighting-db-17", {
        agent.LABEL_OWNER: "true",
        "net.lightingpanel.server-id": "9",
        "net.lightingpanel.database-id": "17",
    })
    db_volume = FakeVolume("lighting-db-data-17", database, {
        agent.LABEL_OWNER: "true",
        "net.lightingpanel.server-id": "9",
        "net.lightingpanel.database-id": "17",
    })
    docker = FakeDocker([db_volume], [db_container])
    game_container = FakeContainer("lighting-server-9", {
        agent.LABEL_OWNER: "true",
        "net.lightingpanel.server-id": "9",
    })

    backup = agent.create_server_backup(docker, 9, game, label="manual")
    assert backup["database_count"] == 1
    assert backup["offsite"] is False
    assert db_container.stop_calls == 1
    assert db_container.start_calls == 1

    (game / "server.properties").write_text("motd=after")
    (database / "base-data").write_text("database-after")
    (database / "new-data").write_text("new")

    restored = agent.restore_server_backup(docker, 9, game_container, game, backup["id"])
    assert restored["database_count"] == 1
    assert (game / "server.properties").read_text() == "motd=before"
    assert (database / "base-data").read_text() == "database-before"
    assert not (database / "new-data").exists()
    assert game_container.status == "running"
    assert db_container.status == "running"


def test_backup_archive_rejects_path_traversal(tmp_path):
    archive_path = tmp_path / "unsafe.tar.gz"
    source = tmp_path / "payload.txt"
    source.write_text("no")
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("../escaped.txt")
        info.size = source.stat().st_size
        with source.open("rb") as stream:
            archive.addfile(info, stream)

    with tarfile.open(archive_path, "r:gz") as archive:
        try:
            agent._validate_backup_members(archive.getmembers())
        except ValueError as exc:
            assert "unsafe archive" in str(exc)
        else:
            raise AssertionError("Path traversal archive entry was accepted")
