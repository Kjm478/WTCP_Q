
import asyncio
import csv
from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, ConnectionTerminated
from pdu import PDU, PDUType
from state_machine import create_server_state_machine, StateMachineError

STREAM_IDS = {
    'control': 0,
    'telemetry': 2,
    'emergency': 4,
}

class WTCPServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, telemetry_file=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_machine = create_server_state_machine()
        self.telemetry = []
        self.telemetry_file = telemetry_file
        self.next_session = 1

    def quic_event_received(self, event):
      
        if isinstance(event, StreamDataReceived):
            pdu = PDU.from_bytes(event.data)
            sid = event.stream_id
            # CONTROL stream
            if sid == STREAM_IDS['control']:
                _, new = self.state_machine.on_pdu(pdu)
                if pdu.pdu_type == PDUType.AUTH_REQUEST:
                    self.send_auth_resp()
                elif pdu.pdu_type == PDUType.CONTROL:
                    print("Received CONTROL:", PDU.parse_control(pdu.payload))
                elif pdu.pdu_type == PDUType.TERMINATE:
                    self.send_terminate()
            # TELEMETRY stream
            elif sid == STREAM_IDS['telemetry']:
                _, new = self.state_machine.on_pdu(pdu)
                self.telemetry.append(PDU.parse_telemetry(pdu.payload))
            self.telemetry_count = getattr(self, 'telemetry_count', 0) + 1
            if self.telemetry_count % 10 == 0:
                ctl = PDU.build_control(pdu.session_id)
                self.send_pdu(ctl)
            # EMERGENCY stream
            elif sid == STREAM_IDS['emergency']:
                _, new = self.state_machine.on_pdu(pdu)
                print("EMERGENCY from client:", PDU.parse_emergency(pdu.payload))
                self.send_terminate()

        elif isinstance(event, ConnectionTerminated):
            self.dump_telemetry()

    def send_pdu(self, pdu):
        sid = {
            PDUType.AUTH_RESPONSE: STREAM_IDS['control'],
            PDUType.CONTROL:   STREAM_IDS['control'],
            PDUType.TELEMETRY_REQUEST: STREAM_IDS['telemetry'],
            PDUType.EMERGENCY: STREAM_IDS['emergency'],
            PDUType.TERMINATE: STREAM_IDS['control'],
        }[pdu.pdu_type]
        self._quic.send_stream_data(sid, pdu.to_bytes(), end_stream=False)

    def send_auth_resp(self):
        sid = self.next_session
        pdu = PDU.build_auth_resp(status=0, session_id=sid)
        self.next_session += 1
        print("Sending AUTH_RESPONSE with payload len:", len(pdu.payload))
        self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)  # transition to OPERATIONAL state
        
        
    def send_terminate(self):
        pdu = PDU(PDUType.TERMINATE, version=1, session_id=0)
        self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)

    def dump_telemetry(self):
        if not self.telemetry:
            return
        # write a CSV of the parsed telemetry dicts
        with open(self.telemetry_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.telemetry[0].keys())
            if f.tell() == 0:
                writer.writeheader()
            writer.writerows(self.telemetry)
            print(f"Telemetry written to {self.telemetry_file}")

async def main():
    config = QuicConfiguration(is_client=False)
    config.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
    await serve(
        host="0.0.0.0", port=4433,
        configuration=config,
        create_protocol=lambda *args, **kwargs: WTCPServerProtocol(*args, telemetry_file="telemetry.csv", **kwargs)
    )
    await asyncio.Event().wait() # keep the server running indefinitely

if __name__ == "__main__":
    print("Starting WTCP server on port 4433...")
    asyncio.run(main())
