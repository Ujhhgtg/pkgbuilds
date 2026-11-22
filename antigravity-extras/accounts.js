function antigravityCtxAccountPanel({ react, auth, useSelect, currentEmail, Section, Rows, Row, Button, authState, supported }) {
    const bridge = window.antigravityCtxAccounts;
    const activity = useSelect(antigravityCtxAccountsActivity);
    const [saved, setSaved] = react.useState([]);
    const [pending, setPending] = react.useState(false);
    const [error, setError] = react.useState("");
    const [loading, setLoading] = react.useState(true);
    const activityNow = react.useRef(activity);
    activityNow.current = activity;
    const current = authState === "signedIn";
    const [resolvedEmail, setResolvedEmail] = react.useState("");
    const email = current ? currentEmail || resolvedEmail : "";
    const refresh = async () => {
        const response = await bridge.list();
        if (response.error) throw new Error(response.error);
        setSaved(response.result);
    };
    react.useEffect(() => {
        if (!bridge || !supported) return;
        refresh().then(() => setError(""), failure => setError(failure.message)).finally(() => setLoading(false));
    }, [bridge, currentEmail, authState, supported]);
    react.useEffect(() => {
        setResolvedEmail("");
        if (!bridge || !supported || !current || currentEmail) return;
        let live = true;
        auth._lsClient?.getUserStatus({}).then(response => {
            if (live) setResolvedEmail(response.userStatus?.email || "");
        }).catch(() => {});
        return () => { live = false; };
    }, [bridge, auth, current, currentEmail, supported]);
    if (!bridge || !supported) return null;

    const sessionReady = current ? Boolean(email) : authState === "signedOut";
    const call = async (method, value) => {
        const response = await bridge[method](value);
        if (response.error) throw new Error(response.error);
        return response.result;
    };
    const run = async (operation, id) => {
        if (pending || loading || (operation === "login" && (activityNow.current !== "idle" || !sessionReady))) return;
        setPending(true);
        setError("");
        let previous;
        let activated = false;
        try {
            if (operation === "remove") {
                await call("remove", id);
            } else if (operation === "add") {
                await call("add", email || null);
            } else {
                previous = await call("park", email || null);
                if (activityNow.current !== "idle") throw new Error("Wait for running agents to finish before switching accounts.");
                if (previous) await auth.logout();
                await call("activate", id);
                activated = true;
                await auth.checkCurrentAuthStatus();
                if (auth._authState?.state !== "signedIn") {
                    await auth.showLoginFlow();
                }
            }
        } catch (failure) {
            if (previous && !activated) {
                try {
                    await call("activate", previous);
                    await auth.checkCurrentAuthStatus();
                } catch {
                    setError("Switch failed. Your previous account remains saved; choose Login to restore it.");
                    return;
                }
            }
            setError(failure.message);
        } finally {
            try { await refresh(); } catch (failure) { setError(failure.message); }
            setPending(false);
        }
    };

    const create = react.createElement;
    const blocked = pending || loading || activity !== "idle" || !sessionReady;
    const button = (label, disabled, onClick) => create(Button, { size: "sm", variant: "secondary", disabled, onClick }, label);
    return create(Section, { title: "Switch Accounts" },
        create(Rows, null,
            create(Row, { label: "Add Account", description: "Save another Google account without switching.",
                rightElement: button("Add", pending || loading, () => run("add")) }),
            current && create(Row, { label: email || "Signed-in Google account", rightElement: "Current" }),
            ...saved.filter(account => !email || account.email.toLowerCase() !== email.toLowerCase()).map(account =>
                create(Row, { key: account.id, label: account.email, rightElement:
                    create("div", { className: "flex items-center gap-2" },
                        button("Login", blocked, () => run("login", account.id)),
                        button("Logout", pending || loading, () => run("remove", account.id))) })),
            activity === "busy" && create("div", { className: "px-3 py-2 text-sm text-muted-foreground" }, "Wait for running agents to finish before switching accounts."),
            error && create("div", { className: "px-3 py-2 text-sm text-destructive", role: "alert" }, error)));
}

function antigravityCtxAccountsActivity(state) {
    const summaries = state.trajectorySummaries;
    if (!summaries?.hasLoadedInitialSummaries) return "unknown";
    const running = [summaries.summaries, summaries.externalSummaries].some(group =>
        Object.values(group ?? {}).some(summary => !summary.killed &&
            (summary.hasRunningSubagents || [2, 3, 4].includes(summary.status))));
    return running ? "busy" : "idle";
}
