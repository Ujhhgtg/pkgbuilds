# antigravity-ctx

Build and install with `makepkg -si`. The pacman hook applies the setting in
`/etc/antigravity-ctx.conf` after installing or upgrading either `antigravity` or
`antigravity-ctx`. The package defaults to `cap=600k` (600,000 tokens) and
`stats=off`. Older configs without `stats` also default to `off`.

```sh
sudo /usr/bin/antigravity-ctx cap 512k
sudo /usr/bin/antigravity-ctx stats on
sudo /usr/bin/antigravity-ctx stats off
```

`stats on` adds a ring to the right of the model picker. Hover or focus it to
see estimated token usage and the active conversation's effective limit. It
appears once the conversation has stats and does not change the cap.

`stats off` removes the meter and restores the original renderer JavaScript.
`cap off` restores the stock 256,000-token cap on a supported build. Run both
before uninstalling the helper. To apply a manual config edit, run
`pkexec /usr/bin/antigravity-ctx apply`. Relaunch Antigravity to load changes.

The patch looks for a unique instruction sequence in the executable sections of
the Linux x86-64 server. The sequence was verified on Antigravity Desktop 2.32.1
and 2.33.0 and can match other builds that retain it. If it changes or matches
more than once, the hook skips the binary and retains the configured cap. The
selected model's token budget and output reserve can lower the effective cap.
The optional meter finds the composer by property names and captures minified
identifiers from the renderer. It was verified on 2.32.1 and 2.33.0. If enabled
and its renderer anchors do not match uniquely, no binary changes are made.
