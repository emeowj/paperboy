"""Settings: one JSON file in the data directory (PAPERBOY_DATA, default /data).

{
  "instapaper": {"access_token"},          optional; a personal access token (API v2).
                                           Or, until xAuth ends on 2027-09-30, the old
                                           {"consumer_key", "consumer_secret", "username", "password"}
  "feedbin":    {"email", "password"},                                        optional
  "public_url": "https://host/paperboy",  the address the reader uses (for bundle downloads)
  "archive_at": 95,                        percent read that counts as finished
  "port": 17300,
  "bind": "0.0.0.0",
  "reader_sync": true,                     tidy the reader when it's in File Transfer mode
  "library_author": "",                    if set (e.g. "Paperboy"), every article's EPUB author,
                                           so the Library's Author tab groups them apart from books
  "sync_removes": false,                   Sync all also deletes finished articles from the
                                           reader. Needs firmware with catalog.bundle_remove
  "broadcast": ["255.255.255.255"],        where to look for the reader
  "token": "..."                           added on first start
}

At least one of instapaper / feedbin is required.

Credentials (and the token) can also come from environment variables, which win over
the file, so the file is optional when they cover everything:
  PAPERBOY_INSTAPAPER_ACCESS_TOKEN
  PAPERBOY_INSTAPAPER_CONSUMER_KEY, _CONSUMER_SECRET, _USERNAME, _PASSWORD   (legacy xAuth)
  PAPERBOY_FEEDBIN_EMAIL, PAPERBOY_FEEDBIN_PASSWORD
  PAPERBOY_TOKEN
  PAPERBOY_PUBLIC_URL, PAPERBOY_READER_SYNC (true/false)
Values from the environment are never written to config.json.
"""
import json
import os
import secrets

DATA_DIR = os.environ.get("PAPERBOY_DATA", "/data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULTS = {
    "archive_at": 95,
    "port": 17300,
    "bind": "0.0.0.0",
    "reader_sync": True,
    "broadcast": ["255.255.255.255"],
    "public_url": "",
    "library_author": "",
    "sync_removes": False,
}


class ConfigError(Exception):
    pass


def data_path(*parts):
    return os.path.join(DATA_DIR, *parts)


ENV_SECTIONS = {
    "instapaper": ("access_token", "consumer_key", "consumer_secret", "username", "password"),
    "feedbin": ("email", "password"),
}


def _from_env(cfg):
    """Return a copy of cfg with credentials from PAPERBOY_* environment variables merged in."""
    cfg = dict(cfg)
    for section, keys in ENV_SECTIONS.items():
        found = {k: os.environ[f"PAPERBOY_{section.upper()}_{k.upper()}"]
                 for k in keys if os.environ.get(f"PAPERBOY_{section.upper()}_{k.upper()}")}
        if found:
            cfg[section] = {**(cfg.get(section) or {}), **found}
    if os.environ.get("PAPERBOY_TOKEN"):
        cfg["token"] = os.environ["PAPERBOY_TOKEN"]
    if os.environ.get("PAPERBOY_PUBLIC_URL"):
        cfg["public_url"] = os.environ["PAPERBOY_PUBLIC_URL"]
    if os.environ.get("PAPERBOY_READER_SYNC"):
        cfg["reader_sync"] = os.environ["PAPERBOY_READER_SYNC"].strip().lower() in ("1", "true", "yes", "on")
    return cfg


def load():
    try:
        with open(CONFIG_PATH) as f:
            file_cfg = json.load(f)
    except FileNotFoundError:
        file_cfg = None
    except ValueError as e:
        raise ConfigError(f"{CONFIG_PATH} is not valid JSON: {e}")

    cfg = _from_env(file_cfg or {})
    if file_cfg is None and not (cfg.get("instapaper") or cfg.get("feedbin")):
        raise ConfigError(f"no config file at {CONFIG_PATH} and no PAPERBOY_INSTAPAPER_* / "
                          "PAPERBOY_FEEDBIN_* environment variables (see the README)")

    ip, fb = cfg.get("instapaper"), cfg.get("feedbin")
    if not ip and not fb:
        raise ConfigError("config needs an \"instapaper\" section, a \"feedbin\" section, or both "
                          "(or PAPERBOY_INSTAPAPER_* / PAPERBOY_FEEDBIN_* environment variables)")
    if ip and not ip.get("access_token"):
        missing = [k for k in ("consumer_key", "consumer_secret", "username", "password") if not ip.get(k)]
        if len(missing) == 4:
            raise ConfigError("instapaper section needs an \"access_token\" (a personal access token from "
                              "instapaper.com/developers/applications)")
        if missing:
            raise ConfigError("instapaper section is missing: " + ", ".join(missing))
    if fb:
        missing = [k for k in ("email", "password") if not fb.get(k)]
        if missing:
            raise ConfigError("feedbin section is missing: " + ", ".join(missing))

    if not cfg.get("token"):
        cfg["token"] = secrets.token_urlsafe(24)
        # Persist only what came from the file plus the token, never env secrets.
        persisted = dict(file_cfg or {}, token=cfg["token"])
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(persisted, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG_PATH)
        print(f"Paperboy: added a new token to {CONFIG_PATH}; enter it on the reader.", flush=True)

    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)
    cfg["public_url"] = (cfg.get("public_url") or "").rstrip("/")
    return cfg
