# WTCP‑Q Prototype
 
> **Goal:**  the WTCP‑Q protocol secure handshake, fixed‑rate telemetry, remote rate control, and emergency alerts without extra bells and whistles.

---

## ✨ Implemented.

| Category | Implemented | Notes |
| --- | --- | --- |
| **Transport** | QUIC + TLS 1.3 (`aioquic`) | Single self‑signed cert (`cert.pem` / `key.pem`). |
| **Streams** | `DATA` (unidirectional) & `ALERT` (unidirectional) + control on Stream 0 | Priorities follow QUIC defaults. |
| **PDUs** | `TELEMETRY`, `CONTROL:update_sampling_rate`, `EMERGENCY` | Framed with 2‑byte length prefix. |
| **State machine** | `INIT → OPERATIONAL → CLOSED` | Invalid transitions close the connection. |
| **Client loop** | Sends TELEMETRY every *n* seconds (default 1 Hz); Ctrl‑C triggers EMERGENCY | Configurable via CLI flags. |
| **Server ingest** | Stores packets in‑memory, dumps `telemetry.csv` on shutdown | Prints `***ALERT***` with GPS on EMERGENCY. |
| **Keep‑alive** | 30 s idle timeout (relies on QUIC idle timer) | No ping messages yet. |




---

## 🗂️ Project Layout

```
.
├── client.py          # Async QUIC client (telemetry sender)
├── server.py          # Async QUIC server (telemetry collector)
├── pdu.py             # Packet definitions + encode/decode helpers
├── state_machine.py   # Tiny 3‑state DFA
├── test.py            # Unit + integration tests (pytest)
├── cert.pem / key.pem # Self‑signed cert pair (demo only)
└── README.md          # You are here
```

---

## 🚀 Quick Start

### 1  Prerequisites

* Python **3.10+**
* `pip` & build tools (Linux: `libssl-dev python3-dev`)  
* (Optional) `virtualenv` for isolation

### 2  Clone & install

```bash
# Clone the repo
$ git clone https://github.com/Kjm478/WTCP_Q.git
$ cd WTCP_Q

# Create & activate venv (recommended)
$ python3 -m venv .venv && source .venv/bin/activate

# Install deps – only aioquic 
$ pip install -r requirements.txt 
```

> **Tip:** On Windows/macOS the `aioquic` wheel ships with OpenSSL, so no extra steps are needed.

### 3  Generate a new cert (optional)

The repo ships with a throw‑away pair. To regenerate:

```bash
$ openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem \
    -days 365 -subj "/CN=localhost"
```

### 4  Run the demo

Terminal 1 – **server**
```bash
$ python server.py --host 0.0.0.0 --port 4433
```

Terminal 2 – **client** (send 1 Hz telemetry; Ctrl‑C sends emergency)
```bash
$ python client.py --server 127.0.0.1 --port 4433 \
                   --device-id C1 --rate 1
```

Sample server output:
```
```
`telemetry.csv` is written. .

---

## 🧪 Testing

```bash
# Run unit + integration tests (expect <5 s)
$ pytest -q
```

---

## 📄 License

MIT – see `LICENSE` file. The demo certificate key pair is **for testing only**; generate your own for anything public.
