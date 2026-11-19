# DeckLink

A lightweight Stream Deck-style dashboard for controlling a PC from a phone or tablet on the same local network. The host uses Python's standard library; the web client is plain HTML, CSS, and JavaScript designed to stay usable on older Android browsers.

**Working title only:** DeckLink is a temporary project name. Check GitHub, domain, and trademark availability before publishing under it.

## What is included

- Live CPU, memory, system disk, and network transfer stats
- Responsive dark touch interface and connection status
- Pairing token required for stats and action requests
- Configurable buttons for opening URLs and launching configured apps
- No shell command or executable can be sent by the browser

## Start on Windows

1. Install Python 3.9 or newer and extract/clone this folder somewhere convenient.
2. Double-click `start.bat`. The first run creates a pairing token in `config.json` and opens the dashboard on this PC.
3. On your tablet, connect to the same Wi-Fi and open the full address shown in the DeckLink window. The address includes the pairing token. If prompted by Windows Firewall, allow Python on **Private networks** so your tablet can connect.
4. Keep the DeckLink window open while using the dashboard. Press Ctrl+C there to stop it.

You can also run `python host.py --no-open` to start without opening a browser, or `python host.py --port 8765` to choose a port.

## Add or edit buttons

Edit `config.json` while DeckLink is stopped, then start it again. IDs must be unique. Supported action forms:

```json
{"id":"docs","label":"Open docs","icon":"▤","type":"url","url":"https://example.com"}
```

```json
{"id":"editor","label":"Open editor","icon":"✎","type":"app","executable":"notepad.exe","args":[]}
```

The app's executable and argument list are trusted local configuration. Only the matching button ID is accepted from the tablet. Keep app arguments fixed and review them before use. URL actions open HTTP/HTTPS links in the PC's default browser.

## Pairing and network notes

The token is generated on first start, stored in `config.json`, and required for stats and actions. Treat it like a password. Use the dashboard only on a trusted private Wi-Fi network; this first version uses plain HTTP on the local network, so do not forward its port to the public internet. To rotate the token, stop the host, clear the `token` value in `config.json`, and restart.

If Windows Firewall blocks the tablet, allow Python on a private network or adjust the firewall for the selected port. Guest Wi-Fi and client isolation can prevent devices from seeing each other.

## Platform notes

The host is cross-platform Python. CPU/memory stats use Windows system APIs or Linux `/proc`; disk and network support are best-effort. The included starter buttons target Windows. Change `config.json` for apps available on your platform. No external Python packages are required.

## GitHub first version

The folder is ready to initialize as a Git repository. Before publishing, rotate the pairing token if the config contains a real one and review the action list for your machine. Do not commit a live token.

## License

No license has been selected yet. Add one before inviting contributions or presenting the repository as open source.
