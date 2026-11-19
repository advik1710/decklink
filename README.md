# DeckLink

A lightweight PC dashboard for an Android phone or tablet on the same local network. The Python host uses the standard library; the web interface is plain HTML, CSS, and JavaScript which works on any browsers, no matter how old.


## Start on Windows

1. Install Python 3.9 or newer.
2. Double-click `manage.bat` to open the native desktop manager. Use **Start host** to run DeckLink and open the dashboard. The host window shows the tablet link and pairing token.
3. On your tablet, connect to the same Wi-Fi and open the pairing link shown by the manager or host window. Allow Python through Windows Firewall on **Private networks** if prompted.
4. Leave the host running while using the dashboard. Stop it in the manager or press Ctrl+C in the host window.

You can also double-click `start.bat` to run the host without the manager, or run `python host.py --no-open` / `python host.py --port 8765`.

To run the host without leaving a terminal open, double-click `start-headless.bat`. It writes output to `decklink-host.log` and errors to `decklink-error.log`. Double-click `stop.bat` to stop that background host.

## Dashboard

- CPU, memory, disk, and network stat cards on the left side of desktop layouts
- Select a stat card to show its live history graph; CPU is selected by default, and the graph switches to the selected metric
- Shortcut panel on the right, with six buttons per page; use arrows, page dots, or swipe horizontally
- On small screens the stats and shortcut panel stack vertically for portrait use
- Flat charcoal styling with subdued color accents and no glow effects

## Manage shortcuts

Open `manage.bat`. Select **Add new**, enter a label and optional icon, choose URL or App, fill in the target, then select **Save button**. Select an existing button to edit it. Use **Remove**, **Move up**, and **Move down** to maintain the list and order. There is no fixed shortcut count; the dashboard divides buttons into six-button pages. Changes sync when the dashboard refreshes (within about ten seconds).

URL buttons must use `http://` or `https://`. App buttons store a fixed executable and optional arguments, one argument per line. The browser sends only a configured button ID, never a command. The included example app button opens Notepad on Windows.

## Profiles, layouts, and appearance

The desktop manager supports named shortcut profiles and JSON layout import/export. Export files contain shortcut layouts only and do not include the host pairing token. Import validates the layout and asks before replacing profiles. In the browser, use **Theme** and **Button size** to switch between dark/light and compact/large controls; those choices are saved on that device.

The manager also has an opt-in **Start host when I sign in** setting on Windows. It adds only DeckLink's own current-user sign-in entry. Turn it off in the manager to remove it.

The **Find a PC** control currently provides manual address and token entry for another DeckLink host. Automatic network discovery and multiple saved PC profiles are not implemented yet. The fullscreen Now Playing surface is reserved but remains hidden because no playback provider has been selected. GPU temperature is shown as unavailable because no supported sensor provider is configured; missing or zero readings are not presented as real temperatures.

If the host temporarily disconnects, the dashboard keeps its current layout and retries with a bounded delay. Shortcut requests are not queued while disconnected.

## Pairing and network notes

The first host run creates a random token in `config.json`. Treat the pairing link as a password and use it only on a trusted private Wi-Fi network. This first version uses plain HTTP on the local network; do not forward its port to the public internet. Clear the token value in `config.json` and restart the host to rotate it.

If Windows Firewall blocks the tablet, allow Python on a private network or adjust the firewall for the chosen port. Guest Wi-Fi and client isolation can prevent devices from seeing each other.

## Platform notes

The host is cross-platform Python. The desktop manager uses Tkinter, which is included with most standard Windows Python installers. CPU and memory stats use Windows APIs or Linux `/proc`; disk and network are best-effort. Included starter shortcuts target Windows. No third-party Python packages are required.


