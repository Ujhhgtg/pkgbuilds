# antigravity-extras

Quality-of-life features for Antigravity.

## Context Cap

The default is `cap=750k` (750,000 tokens). Set a different cap or restore the
stock limits:

```sh
sudo /usr/bin/antigravity-extras cap 512k
sudo /usr/bin/antigravity-extras cap off
```

The cap also applies to bundled 512K checkpoint profiles and, on 2.33.0 and
2.34.0, to a 512K limit applied later at runtime. Other profile limits don't
change. A model's token budget and output reserve can still lower the effective
cap. `cap off` restores the stock 256,000-token default and 512K profile limits.

The cap patch was verified on Antigravity Desktop 2.32.1, 2.33.0, and 2.34.0
on Linux x86-64. It skips binaries where the expected instructions don't match
uniquely and retains your saved setting.

## Context Meter

The meter is on by default. Turn it on or off with:

```sh
sudo /usr/bin/antigravity-extras stats on
sudo /usr/bin/antigravity-extras stats off
```

The ring appears to the right of the model picker once the conversation has
usage data. Hover or focus it to see the estimated token usage and effective
limit. The meter doesn't change the cap.

The meter was verified on 2.32.1, 2.33.0, and 2.34.0. If its renderer anchors
don't match uniquely, the meter patch is skipped.

## Switch Accounts

Account switching is on by default. It requires `python-gobject`, `libsecret`, a Linux
desktop keyring that provides Secret Service, and native Google sign-in. It
doesn't support file-based credentials or Application Default Credentials.

```sh
sudo /usr/bin/antigravity-extras accounts on
sudo /usr/bin/antigravity-extras accounts off
```

After enabling the patch and relaunching Antigravity Desktop 2.34.0, open
**Settings → Account → Switch Accounts** in a local window.

- **Add** opens Google sign-in in a separate session and saves the new account without switching. You can add accounts while agents are running.
- **Login** activates a saved account without reloading. History, projects, and open panels stay in place.
- **Logout** removes an inactive account from the local keyring; it doesn't log out of Google in the browser or revoke a grant.

Your already signed-in account appears automatically as **Current**. Only
Login waits for running agents to finish. `accounts off` removes the UI
patch but leaves saved accounts in the keyring; remove them first if desired.
