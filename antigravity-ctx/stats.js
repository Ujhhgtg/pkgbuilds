function antigravityCtxRenderStats(react, stateContext, useStateSelector, emptyProvider, Tooltip) {
    const provider = react.useContext(stateContext)?.cascadeContext?.state?.agentStateProvider ?? emptyProvider;
    const usage = useStateSelector(provider, antigravityCtxStatsSelector);
    const tooltipId = react.useId();
    const used = usage?.estimatedTokensUsed;
    const total = usage?.maxContextTokens;
    if (!Number.isFinite(used) || used < 0 || !Number.isFinite(total) || total <= 0) return null;

    const fill = Math.min(100, 100 * used / total);
    const percent = Math.round(fill);
    const format = new Intl.NumberFormat();
    const counts = `${format.format(used)} / ${format.format(total)} tokens used`;
    const circle = { cx: 6, cy: 6, r: 5, stroke: "currentColor", strokeWidth: 2, fill: "none" };
    return react.createElement(react.Fragment, null,
        react.createElement("span", {
            "data-testid": "antigravity-ctx-stats",
            "data-tooltip-id": tooltipId,
            "aria-label": `Context window: ${percent}% full. ${counts}`,
            className: "inline-flex shrink-0 items-center justify-center rounded-full text-muted-foreground",
            role: "img",
            tabIndex: 0,
        }, react.createElement("svg", { width: 12, height: 12, viewBox: "0 0 12 12", "aria-hidden": true },
            react.createElement("circle", { ...circle, opacity: 0.16 }),
            fill > 0 && react.createElement("circle", {
                ...circle,
                transform: "rotate(-90 6 6)",
                strokeLinecap: "round",
                pathLength: 100,
                strokeDasharray: 100,
                strokeDashoffset: 100 - fill,
            })
        )),
        react.createElement(Tooltip, { id: tooltipId, place: "top", openEvents: { mouseenter: true, focus: true } },
            react.createElement("div", { className: "text-center" },
                react.createElement("div", null, "Context window"),
                react.createElement("div", null, `${percent}% full`),
                react.createElement("div", null, counts)
            ))
    );
}
const antigravityCtxStatsSelector = { selector: state => state?.contextWindowUsage };
