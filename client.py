import asyncio
import argparse
import time
import ssl 
from  uuid import  UUID
from aioquic.asyncio import connect, QuicConnectionProtocol 
from aioquic.quic.configuration import QuicConfiguration
from pdu import PDU, PDUType
from state_machine import create_client_state_machine, ClientState, StateMachineError
from aioquic.quic.events import StreamDataReceived
from enum import Enum, auto

STREAM_IDS = {
    "control": 0,
    "telemetry": 2,
    "emergency": 4,
}

class Value(Enum):
    lat = auto()
    battery = auto()
    lon = auto()
    activity = auto()
    flag = auto()
class WTCPClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, session_id, rate, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = session_id
        self.rate = rate
        self.state_machine = create_client_state_machine()
        self.last_pdu_time = time.time()
        
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            try: 
                pdu = PDU.from_bytes(event.data)
                old_state, new_state = self.state_machine.on_pdu(pdu)
                self.last_pdu_time = time.time()
                print(f"Transitioned from {old_state} to {new_state} with PDU: {pdu}")
                if pdu.pdu_type == PDUType.AUTH_RESPONSE:
                    info = PDU.parse_auth_resp(pdu.payload)
                    self.session_id = info['session_id']
                    #start telemetry and idle watchers
                    asyncio.create_task(self.send_telemetry())
                    asyncio.create_task(self.idle_watcher())
                elif pdu.pdu_type == PDUType.CONTROL:
                    print("Received control PDU, processing...")
                    self.handle_control(pdu.payload)
                elif pdu.pdu_type == PDUType.EMERGENCY:
                    print("Emergency PDU received, transitioning to TERMINATING state.")
                    asyncio.create_task(self.send_terminate())
                elif pdu.pdu_type == PDUType.SLEEP: 
                    print("Received SLEEP PDU, transitioning to SLEEPING state.")
                    wake = PDU.parse_sleep(pdu.payload)
                    if wake and self.state_machine.state == ClientState.SLEEPING:
                        print("Waking up from SLEEP state.")
                        self.telemetry_task = asyncio.create_task(self.telemetry_loop())
                    elif not wake and self.telemetry_task:
                        self.telemetry_task.cancel()
                elif pdu.pdu_type == PDUType.WAKE: 
                    pass
            except Exception as e:
                print(f"Error processing PDU: {e}")
                
    def stream_for(self, pdu_type):
        """Return the stream ID for the given PDU type."""
        if pdu_type in (
            PDUType.AUTH_REQUEST,
            PDUType.AUTH_RESPONSE,
            PDUType.CONTROL,
            PDUType.TERMINATE
        ):
            return STREAM_IDS['control']
        elif pdu_type == PDUType.TELEMETRY_REQUEST:
            return STREAM_IDS['telemetry']
        elif pdu_type == PDUType.EMERGENCY:
            return STREAM_IDS['emergency']
        else:
            raise ValueError(f"Unknown PDU type: {pdu_type}")

        
    async def send_pdu(self, pdu):
        sid = self.stream_for(pdu.pdu_type)
        self._quic.send_stream_data(sid, pdu.to_bytes(), end_stream=False)

    async def send_auth(self):
        # replace UUID(int=0) with real device UUID
        pdu = PDU.build_auth_req(UUID(int=0), sampling_rate=int(self.rate), geofence_radius=0.0)
        await self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)

    async def send_telemetry(self):
        while self.state_machine.state == ClientState.OPERATIONAL:
            timestamp = int(time.time())
            pdu = PDU.build_telemetry(self.session_id,timestamp, lat= float(Value.lat.value), lon=float(Value.lon.value),
                                      activity=(Value.activity.value), battery=Value.battery.value, diag_flags=Value.flag.value)
            sid = self.stream_for(pdu.pdu_type)
            print(f"Sending telemetry PDU on stream(ts= {timestamp}) {sid}: {pdu}")
            await self.send_pdu(pdu)
            await asyncio.sleep(self.rate)

    async def send_terminate(self):
        pdu = PDU(PDUType.TERMINATE, version=1, session_id=self.session_id)
        await self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)

    def handle_control(self, payload):
        params = PDU.parse_control(payload)
        if 'sampling_rate' in params:
            old = self.rate
            self.rate = params['sampling_rate']
            print(f"Sampling rate updated: {old} → {self.rate}")
        if 'geofence_radius' in params:
            print(f"Geofence radius updated: {params['geofence_radius']}")

    async def idle_watcher(self):
        while self.state_machine.state == ClientState.OPERATIONAL:
            await asyncio.sleep(1)
            if time.time() - self.last_pdu_time > 120:
                print("Idle timeout — sending TERMINATE")
                await self.send_terminate()
                break

def main():
    parser = argparse.ArgumentParser(description="WTCP-Q Client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--rate", type=float, default=1.0, help="Telemetry interval (s)")
    cli_args = parser.parse_args()

    config = QuicConfiguration(is_client=True)
    config.verify_mode = ssl.CERT_NONE  # Disable cert verification for testing
    asyncio.run(run(cli_args, config))

async def run(cli_args, config):
    async with connect(
        cli_args.host,
        cli_args.port,
        configuration=config,
        create_protocol=lambda *p_args, **p_kwargs: WTCPClientProtocol(*p_args, session_id=cli_args.session_id, rate=cli_args.rate, **p_kwargs)
    ) as client:
        await client.send_auth()
        await client.wait_closed()

if __name__ == "__main__":
    main()