
import asyncio
import csv
from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, ConnectionTerminated
from pdu import PDU, PDUType
from state_machine import create_server_state_machine, StateMachineError
import sys

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
        self.emergencies = []
        self.telemetry_file = "telemetry.csv" if telemetry_file is None else telemetry_file
        self.next_session = 1
        self.wake = asyncio.create_task(self.wake_loop())

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
                self.emergencies.append(PDU.parse_emergency(pdu.payload))
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
        
    async def wake_loop(self):
        while True: 
            await asyncio.sleep(60)  # wake every 60 seconds
            if self.state_machine.state == 'OPERATIONAL':
                pdu = PDU.build_wake(session_id=self.next_session - 1)
                self.send_pdu(pdu)
                print("Sent WAKE PDU to client")
        
        
    def send_terminate(self):
        pdu = PDU(PDUType.TERMINATE, version=1, session_id=0)
        self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)

    def dump_telemetry(self):
        if  self.telemetry:
            # write a CSV of the parsed telemetry dicts
            with open("telemetry.csv", "a", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.telemetry[0].keys())
                if f.tell() == 0:
                    writer.writeheader()
                writer.writerows(self.telemetry)
                print(f"Telemetry written to {self.telemetry_file}")
        if self.emergencies:
            with open("emergency.csv","a",newline="") as f:
                wr = csv.DictWriter(f,self.emergencies[0].keys())
                if f.tell()==0: wr.writeheader()
                wr.writerows(self.emergencies)
                print(f"Emergencies written to emergency.csv")
        
#interactive command line interface for server control
async def stdin_cmd(server: WTCPServerProtocol):
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    while True:
        line = (await reader.readline()).decode().strip().split()
        if not line: continue
        cmd, *args = line
        if cmd == "r" and args:
            server.send_pdu(PDU.build_control(0,new_rate=int(args[0])))
        elif cmd == "g" and args:
            server.send_pdu(PDU.build_control(0,new_radius=float(args[0])))
        elif cmd == "sleep":
            server.send_pdu(PDU.build_sleep(0,wake=False))
        elif cmd == "wake":
            server.send_pdu(PDU.build_sleep(0,wake=True))
        else:
            print("Commands:  r <rate> | g <radius> | sleep | wake")

async def main():
    cfg = QuicConfiguration(is_client=False)
    cfg.load_cert_chain("cert.pem","key.pem")
    server_proto = None
    def factory(*a, **k):
        nonlocal server_proto
        server_proto = WTCPServerProtocol(*a, **k)
        return server_proto
    await serve("0.0.0.0",4433,configuration=cfg,create_protocol=factory)
    print("WTCP server on :4433 —-type 'help' for commands")
    await stdin_cmd(lambda:server_proto)

if __name__ == "__main__":
    print("Starting WTCP server on port 4433...")
    asyncio.run(main())
