from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from gi.repository import Gio, GLib

SECRET_SERVICE = "org.freedesktop.secrets"
SERVICE_PATH = "/org/freedesktop/secrets"
SERVICE_INTERFACE = "org.freedesktop.Secret.Service"
ITEM_INTERFACE = "org.freedesktop.Secret.Item"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
ACTIVE = {"service": "gemini", "username": "antigravity"}
SAVED = "antigravity-ctx-accounts"
EMAIL_FIELD = "antigravity-ctx-email"
SERVER = "/opt/Antigravity/resources/bin/language_server"
TOKEN_FILE = ".gemini/jetski-standalone-oauth-token"


class AccountError(ValueError):
    pass


class Keyring:
    def __init__(self, bus):
        self.bus = bus

    def call(self, path, interface, method, signature=None, arguments=()):
        parameters = GLib.Variant(signature, arguments) if signature else None
        return self.bus.call_sync(SECRET_SERVICE, path, interface, method, parameters,
                                  None, Gio.DBusCallFlags.NONE, 4000, None).unpack()

    def search(self, attributes):
        unlocked, locked = self.call(SERVICE_PATH, SERVICE_INTERFACE, "SearchItems", "(a{ss})", (attributes,))
        if locked:
            raise AccountError("Unlock your system keyring, then try again.")
        return unlocked

    def active(self):
        items = self.search(ACTIVE)
        if len(items) > 1:
            raise AccountError("More than one Antigravity credential matches the active account.")
        return items[0] if items else None

    def attributes(self, item):
        return self.call(item, PROPERTIES_INTERFACE, "Get", "(ss)", (ITEM_INTERFACE, "Attributes"))[0]

    def update(self, item, attributes):
        self.call(item, PROPERTIES_INTERFACE, "Set", "(ssv)",
                  (ITEM_INTERFACE, "Attributes", GLib.Variant("a{ss}", attributes)))

    def saved(self):
        accounts = []
        for item in self.search({"service": SAVED}):
            attributes = self.attributes(item)
            label = attributes.get(EMAIL_FIELD, "")
            identifier = attributes.get("username", "")
            if re.fullmatch(r"[a-f0-9]{32}", identifier) and valid_email(label):
                accounts.append({"id": identifier, "email": label})
        return sorted(accounts, key=lambda account: account["email"].casefold())

    def item(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise AccountError("Invalid saved account.")
        items = self.search({"service": SAVED, "username": identifier})
        if len(items) != 1 or not valid_email(self.attributes(items[0]).get(EMAIL_FIELD)):
            raise AccountError("The saved account is unavailable.")
        return items[0]

    def delete(self, item):
        prompt, = self.call(item, ITEM_INTERFACE, "Delete")
        if prompt != "/":
            raise AccountError("The system keyring requires confirmation to remove this account.")

    def park(self, email):
        active = self.active()
        if not active:
            if email:
                raise AccountError("The current account is not stored in the system keyring.")
            return None
        if not valid_email(email):
            raise AccountError("Wait for Antigravity to load your account email.")
        identifier = uuid4().hex
        attributes = self.attributes(active)
        self.update(active, attributes | {"service": SAVED, "username": identifier, EMAIL_FIELD: email})
        return identifier

    def activate(self, identifier):
        if self.active():
            raise AccountError("Antigravity is already signed in. Try switching again.")
        item = self.item(identifier)
        attributes = self.attributes(item)
        attributes.pop(EMAIL_FIELD)
        self.update(item, attributes | ACTIVE)

    def save(self, email, credential):
        identifier = uuid4().hex
        try:
            subprocess.run(
                ["/usr/bin/secret-tool", "store", "--label=Antigravity saved account",
                 "service", SAVED, "username", identifier, EMAIL_FIELD, email],
                input=credential, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=True,
            )
        except (OSError, subprocess.SubprocessError):
            raise AccountError("Could not save the account in your system keyring.") from None


def acquire_account():
    with tempfile.TemporaryDirectory(prefix="antigravity-extras-login-") as directory:
        home = Path(directory)
        nonce = uuid4().hex
        environment = {name: value for name, value in os.environ.items()
                       if not name.startswith(("GOOGLE_", "GEMINI_", "AGY_", "CODEIUM_", "JETSKI_", "ANTIGRAVITY_"))}
        environment.update(HOME=directory, XDG_CONFIG_HOME=str(home / "config"),
                           XDG_DATA_HOME=str(home / "data"), XDG_CACHE_HOME=str(home / "cache"),
                           XDG_STATE_HOME=str(home / "state"), DBUS_SESSION_BUS_ADDRESS="disabled:",
                           ANTIGRAVITY_VSCODE_HOST="1")
        args = [SERVER, "--standalone", "--subclient_type", "hub", "--override_ide_name", "antigravity",
                "--override_user_agent_name", "antigravity", "--https_server_port", "0", "--csrf_token", nonce,
                "--app_data_dir", "antigravity-extras-login", "--api_server_url", "https://generativelanguage.googleapis.com",
                "--cloud_code_endpoint", "https://daily-cloudcode-pa.googleapis.com"]
        with (home / "startup.log").open("w+b") as log, ThreadPoolExecutor(max_workers=1) as executor:
            with subprocess.Popen(args, env=environment, stdin=subprocess.PIPE, stdout=log, stderr=log) as server:
                try:
                    port = None
                    for _ in range(50):
                        log.seek(0)
                        listener = re.search(rb"listening on random port at (\d+) for HTTP\b", log.read(131072))
                        if listener:
                            port = int(listener[1])
                            break
                        if server.poll() is not None:
                            break
                        time.sleep(0.1)
                    if not port:
                        raise AccountError("Could not start the separate Google sign-in session.")
                    opener = build_opener(ProxyHandler({}))

                    def request(method, timeout=5):
                        url = f"http://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/{method}"
                        req = Request(url, data=b"{}", headers={"Content-Type": "application/json",
                                      "Connect-Protocol-Version": "1", "x-codeium-csrf-token": nonce})
                        with opener.open(req, timeout=timeout) as response:
                            return json.load(response)

                    login = executor.submit(request, "Login", 180)
                    for _ in range(50):
                        if login.done():
                            break
                        url = request("GetLoginSession").get("authUrl")
                        if url:
                            parsed = urlsplit(url)
                            if parsed.netloc != "accounts.google.com" or parsed.scheme != "https" or not parsed.path.startswith("/o/oauth2/"):
                                raise AccountError("Antigravity returned an unexpected Google sign-in URL.")
                            print(json.dumps({"open": url}), flush=True)
                            break
                        time.sleep(0.1)
                    else:
                        raise AccountError("Google sign-in did not start. Try again.")

                    if not login.result().get("authResult", {}).get("hasValidAuth"):
                        raise AccountError("Google sign-in did not finish. No account was added.")
                    email = request("GetUserStatus", 15).get("userStatus", {}).get("email")
                    token = home / TOKEN_FILE
                    if not valid_email(email) or not token.is_file() or not 0 < token.stat().st_size < 65536:
                        raise AccountError("Could not identify or save the signed-in Google account.")
                    credential = token.read_bytes()
                    if not isinstance(json.loads(credential), dict):
                        raise AccountError("Antigravity returned an unsupported credential format.")
                    return email, credential
                finally:
                    if server.poll() is None:
                        server.terminate()
                        try:
                            server.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            server.kill()


def add(keyring, current_email):
    if not Path("/usr/bin/secret-tool").is_file():
        raise AccountError("Install libsecret to add another Google account.")
    saved = keyring.saved()
    email, credential = acquire_account()
    if any(email.casefold() == existing.casefold()
           for existing in [current_email if valid_email(current_email) else "", *(account["email"] for account in saved)]):
        raise AccountError("This Google account is already listed.")
    keyring.save(email, credential)
    return None


def valid_email(email):
    return isinstance(email, str) and re.fullmatch(r"[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+", email) and len(email) <= 254


def handle(keyring, request):
    action = request.get("action")
    if action == "list":
        return keyring.saved()
    if action == "add":
        return add(keyring, request.get("email"))
    if action == "remove":
        keyring.delete(keyring.item(request.get("id")))
        return None
    if action not in {"park", "activate"}:
        raise AccountError("Unknown account action.")
    if (Path.home() / TOKEN_FILE).exists():
        raise AccountError("Switch Accounts requires native Google sign-in stored in the system keyring.")
    if action == "activate":
        keyring.activate(request.get("id"))
        return None
    return keyring.park(request.get("email"))


def terminate(_signal, _frame):
    raise SystemExit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    try:
        request = json.load(sys.stdin)
        result = handle(Keyring(Gio.bus_get_sync(Gio.BusType.SESSION)), request)
        print(json.dumps({"result": result}))
    except AccountError as error:
        print(json.dumps({"error": str(error)}))
    except (OSError, subprocess.SubprocessError):
        print(json.dumps({"error": "Google sign-in did not finish. No account was added."}))
    except (GLib.Error, ValueError, TypeError, AttributeError):
        print(json.dumps({"error": "Could not access the system keyring."}))
