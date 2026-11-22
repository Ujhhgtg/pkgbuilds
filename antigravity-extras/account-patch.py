import hashlib
import json
import re
import struct

IDENTIFIER = rb"[$A-Za-z_][$\w]*"
PAYLOAD_START = b"\n/* antigravity-ctx accounts start */\n"
PAYLOAD_END = b"\n/* antigravity-ctx accounts end */\n"
MOUNT_START = b"/* antigravity-ctx account panel start */"
MOUNT_END = b"/* antigravity-ctx account panel end */"
ACCOUNT_TITLE = rb',\{title:"Account",description:"Manage your plan, credentials, and general preferences\."\},'


def unique(pattern, source, label):
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise ValueError(f"account switcher {label} anchor is missing or ambiguous")
    return matches[0]


def unpatch(source, start, end):
    if start not in source and end not in source:
        return source
    match = unique(re.escape(start) + rb"(?s:.*?)" + re.escape(end), source, "previous patch")
    return source[:match.start()] + source[match.end():]


def patch_renderer(source, payload):
    source = unpatch(unpatch(source, PAYLOAD_START, PAYLOAD_END), MOUNT_START, MOUNT_END)
    if payload is None:
        return source
    title = unique(ACCOUNT_TITLE, source, "Account page")
    react = unique(rb"(?P<react>" + IDENTIFIER + rb")\.createElement\(" + IDENTIFIER + rb"$",
                   source[title.start() - 200:title.start()], "React binding")["react"]
    preceding = source[max(0, title.start() - 4500):title.start()]
    auth = unique(rb"\b(?P<auth>" + IDENTIFIER + rb")=" + IDENTIFIER + rb"\(\)\.core\.authService,",
                  preceding, "authentication service")["auth"]
    account = unique(
        rb"(?<![$\w])(?P<user>" + IDENTIFIER + rb")=(?P<select>" + IDENTIFIER + rb")\(" + IDENTIFIER + rb"\),"
        + rb"(?P<auth_state>" + IDENTIFIER + rb")=(?P=select)\(" + IDENTIFIER + rb"\),"
        + IDENTIFIER + rb'=(?P=auth_state)\?\.state\?\?"signedOut"',
        preceding, "account store",
    )
    page = source[title.end():title.end() + 3600]
    element = re.escape(react + b".createElement(")
    layout = unique(element + rb"(?P<section>" + IDENTIFIER + rb'),\{title:"General"\},'
                    + element + rb"(?P<rows>" + IDENTIFIER + rb"),null,", page, "section layout")
    widgets = unique(element + rb"(?P<row>" + IDENTIFIER + rb'),\{label:"Email",description:'
                     + re.escape(account["user"]) + rb"\?\.email,rightElement:.{1,300}?"
                     + element + rb"(?P<button>" + IDENTIFIER + rb'),\{variant:"secondary",size:"sm"',
                     page, "account widgets")
    mount = (MOUNT_START + react + b".createElement(antigravityCtxAccountPanel,{react:" + react + b",auth:" + auth
             + b",useSelect:" + account["select"] + b",currentEmail:" + account["user"] + b"?.email,authState:"
             + account["auth_state"] + b'?.state??"signedOut",supported:!' + account["user"] + b"?.isAdc&&!"
             + account["auth_state"] + b"?.context?.isGcpTos,Section:" + layout["section"] + b",Rows:" + layout["rows"]
             + b",Row:" + widgets["row"] + b",Button:" + widgets["button"] + b"})," + MOUNT_END)
    return source[:title.end()] + mount + source[title.end():] + PAYLOAD_START + payload + PAYLOAD_END


def patch_asar(source, payload):
    _, header_size, _, json_size = struct.unpack_from("<4I", source)
    header = json.loads(source[16:16 + json_size])
    start = 8 + header_size
    files = []

    def visit(entries):
        for entry in entries.values():
            if "files" in entry:
                visit(entry["files"])
            elif "offset" in entry:
                files.append(entry)

    visit(header["files"])
    dist = header["files"]["dist"]["files"]
    targets = (dist["main.js"], dist["preload.js"])
    contents = bytearray()
    changed = False
    previous_end = 0
    for entry in sorted(files, key=lambda item: (int(item["offset"]), item["size"])):
        offset, size = int(entry["offset"]), entry["size"]
        if offset != previous_end or start + offset + size > len(source):
            raise ValueError("unexpected Antigravity ASAR layout")
        data = source[start + offset:start + offset + size]
        if any(entry is target for target in targets):
            if b'require("electron")' not in data:
                raise ValueError("account switcher Electron anchor is missing")
            updated = unpatch(data, PAYLOAD_START, PAYLOAD_END)
            if payload is not None:
                updated += PAYLOAD_START + payload + PAYLOAD_END
            if updated != data:
                data = updated
                changed = True
                integrity = entry.get("integrity")
                if integrity:
                    block_size = integrity["blockSize"]
                    digest = lambda value: hashlib.sha256(value).hexdigest()
                    integrity.update(hash=digest(data), blocks=[digest(data[index:index + block_size])
                                                               for index in range(0, len(data), block_size)])
        entry.update(offset=str(len(contents)), size=len(data))
        contents.extend(data)
        previous_end = offset + size

    if not changed:
        return source
    if start + previous_end != len(source):
        raise ValueError("unexpected trailing data in Antigravity ASAR")
    encoded = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode()
    padded = encoded + bytes(-len(encoded) % 4)
    return struct.pack("<4I", 4, len(padded) + 8, len(padded) + 4, len(encoded)) + padded + contents
