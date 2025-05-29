import asyncio
import argparse
from aioquic.asyncio import connect, QuicConnectionProtocol 
from aioquic.quic.configuration import QuicConfiguration
from pdu import PDU, PDUType
from state_machine import create_client_state_machine, ClientState, StateMachineError
from aioquic.quic.events import StreamDataReceived

class WTCPClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, session_id, rate, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = session_id
        self.rate = rate
        self.state_machine = create_client_state_machine()
        
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            try: 
                pdu = PDU.from_bytes(event.data)
                old_state, new_state = self.state_machine.on_pdu(pdu)
                print(f"Transitioned from {old_state} to {new_state} with PDU: {pdu}")
                if pdu.pdu_type == PDUType.AUTH_RESPONSE:
                    asyncio.create_task(self.send_telemetry())
                elif pdu.pdu_type == PDUType.CONTROL:
                    print("Received control PDU, processing...")
                    self.handle_control(pdu.payload)
                elif pdu.pdu_type == PDUType.EMERGENCY:
                    print("Emergency PDU received, transitioning to TERMINATING state.")
                    asyncio.create_task(self.send_terminate())
            except Exception as e:
                print(f"Error processing PDU: {e}")
                
    async def send_pdu(self, pdu): 
        stream_id = 0 
        self._quic.send_stream_data(stream_id, pdu.to_bytes(), end_stream = False)
        await self._loop.sock_sendall(b'')
        
    async def send_auth(self): 
        pdu = PDU(PDUType.AUTH_REQUEST, version=1, session_id=self.session_id)
        await self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)
        
    async def send_telemetry(self):
        while self.state_machine.state == ClientState.OPERATIONAL:
            payload = b''
            pdu = PDU(PDUType.TELEMETRY_REQUEST, version=1, session_id=self.session_id, payload=payload)
            await self.send_pdu(pdu)
            await asyncio.sleep(self.rate)
            
    async def send_terminate(self):
        pdu = PDU(PDUType.TERMINATE, version=1, session_id=self.session_id)
        await self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)
        print("Sent terminate PDU, transitioning to TERMINATED state.")


def main():
    parser = argparse.ArgumentParser(description="WTCP-Q Client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--rate", type=float, default=1.0, help="Telemetry send rate (s)")
    args = parser.parse_args()
    configuration = QuicConfiguration(is_client=True)
    asyncio.run(run(args, configuration))

async def run(args, configuration):
    async with connect(
        args.host,
        args.port,
        configuration=configuration,
        create_protocol=lambda *a, **k: WTCPClientProtocol(*a, session_id=args.session_id, rate=args.rate, **k)
    ) as client:
        # send auth once connection is established
        await client._protocol.send_auth()
        await client.wait_closed()

if __name__ == "__main__":
    main()
        

