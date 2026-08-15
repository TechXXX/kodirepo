import sys

try:
    from urllib.parse import parse_qsl
except ImportError:  # pragma: no cover - Kodi 18 compatibility if backported.
    from urlparse import parse_qsl

from resources.lib.uploader import log, manual_upload_entrypoint


def _query_params():
    raw_query = ""
    if len(sys.argv) > 2:
        raw_query = (sys.argv[2] or "").lstrip("?")
    return dict(parse_qsl(raw_query))


def run():
    action = _query_params().get("action", "")
    log("Plugin route invoked: %s" % (action or "<none>"))
    if action == "upload_now":
        manual_upload_entrypoint()
        return
    log("Unknown plugin action: %s" % (action or "<none>"), level="warning")


if __name__ == "__main__":
    run()
