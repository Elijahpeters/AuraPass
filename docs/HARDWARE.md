# AuraPass controller protocol

AuraPass uses newline-delimited ASCII commands at 9600 baud. The local bridge listens on UDP `127.0.0.1:9090` by default and forwards each message to the configured serial port.

| Command | Meaning | Controller behaviour |
| --- | --- | --- |
| `V,<student-id>,<course>` | Show a verified identity/course | Updates the two-line LCD before the grant command. |
| `O,<seat>` | Grant/open | Sets the granted indicators, sounds the success pattern, energizes the relay, and displays the seat. |
| `C` | Close/deny/reset | De-energizes the relay, shows the locked state, and enables the denied indicator. |
| `F` | Hall full | Keeps the relay locked, sounds the error tone, and displays the full-hall state. |

For a grant, the application sends `V` and then `O`. Unknown, ineligible, ambiguous, and repeat scans send `C`. Capacity denial sends `F`.

## Configuration

```powershell
$env:AURAPASS_SERIAL_PORT = "COM3"
$env:AURAPASS_BAUD_RATE = "9600"
$env:AURAPASS_UDP_HOST = "127.0.0.1"
$env:AURAPASS_UDP_PORT = "9090"
python tools\proteus_bridge.py
```

Equivalent command-line overrides are available:

```powershell
python tools\proteus_bridge.py --serial-port COM3 --baud 9600 --host 127.0.0.1 --udp-port 9090
```

## Electrical/co-simulation scope

The retained Proteus project models an Arduino Uno, 16×2 LCD, status LEDs, buzzer, relay/transistor driver and DC-motor load. `firmware/gate.ino` implements the current `V/O/C/F` protocol.

This repository does not claim a fabricated enclosure, production power design, safety certification, physical tamper resistance, or deployment-grade actuator. Proteus and virtual serial software are third-party tools and are not bundled.

## Known protocol limitations

- No acknowledgement or controller readback.
- No checksum or framing beyond newline termination.
- No encryption, authentication, replay protection, or sequence number.
- `V` displays the identifier; deployments should replace this with a non-sensitive display token.
- Invalid commands are ignored by the firmware.
- A local UDP send only confirms that the datagram was handed to the operating system.
