(() => {
    const { contextBridge, ipcRenderer, ipcMain, shell } = require("electron");
    const channel = "antigravity-ctx:accounts";
    if (process.type === "renderer") {
        if (process.isMainFrame) {
            contextBridge.exposeInMainWorld("antigravityCtxAccounts", {
                list: () => ipcRenderer.invoke(channel, { action: "list" }),
                add: email => ipcRenderer.invoke(channel, { action: "add", email }),
                park: email => ipcRenderer.invoke(channel, { action: "park", email }),
                activate: id => ipcRenderer.invoke(channel, { action: "activate", id }),
                remove: id => ipcRenderer.invoke(channel, { action: "remove", id }),
            });
        }
        return;
    }
    const { execFile } = require("node:child_process");
    const { createInterface } = require("node:readline");
    const { getLocalHubWindows, getHubWebContents } = require("./utils");
    const { getLsPort } = require("./languageServer");
    let running = false;
    ipcMain.handle(channel, async (event, request) => {
        const frame = event.senderFrame;
        if (!frame || frame !== event.sender.mainFrame ||
            new URL(frame.url).origin !== `https://127.0.0.1:${getLsPort()}` ||
            !getLocalHubWindows().some(window => getHubWebContents(window) === event.sender)) {
            throw new Error("Switch Accounts is only available in a local Antigravity window.");
        }
        const { action, id, email } = request ?? {};
        if (!["list", "add", "park", "activate", "remove"].includes(action) ||
            (id !== undefined && (typeof id !== "string" || id.length !== 32)) ||
            (email != null && (typeof email !== "string" || email.length > 254))) {
            throw new Error("Invalid account request.");
        }
        if (running) throw new Error("Another account operation is in progress. Try again.");
        running = true;
        try {
            return await new Promise(resolve => {
                let browserFailed = false;
                const child = execFile("/usr/bin/python", ["-I", "/usr/share/antigravity-extras/account-keyring.py"],
                    { timeout: action === "add" ? 210000 : 15000, maxBuffer: 65536 }, (error, output) => {
                        if (browserFailed) {
                            resolve({ error: "Could not open the Google sign-in page." });
                            return;
                        }
                        if (!error) {
                            try { resolve(JSON.parse(output.trimEnd().split("\n").at(-1))); return; } catch {}
                        }
                        resolve({ error: action === "add" ? "Google sign-in did not finish. No account was added." :
                            "Could not access the system keyring. Check that python-gobject is installed." });
                    });
                if (action === "add") {
                    createInterface({ input: child.stdout }).on("line", async line => {
                        try {
                            const message = JSON.parse(line);
                            if (!message.open) return;
                            const url = new URL(message.open);
                            if (url.origin !== "https://accounts.google.com" || !url.pathname.startsWith("/o/oauth2/")) {
                                throw new Error("Unexpected Google sign-in URL.");
                            }
                            await shell.openExternal(url.href);
                        } catch {
                            browserFailed = true;
                            child.kill();
                        }
                    });
                }
                child.stdin.on("error", () => {});
                child.stdin.end(JSON.stringify({ action, id, email }));
            });
        } finally {
            running = false;
        }
    });
})();
