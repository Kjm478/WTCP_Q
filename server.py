import asyncio
import csv 
from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration    
from pdu import PDU, PDUType
from state_machine import create_server_state_machine, ServerState, StateMachineError
from aioquic.quic.events import StreamDataReceived, ConnectionTerminated

class WTCPServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, telemetry_file= None, **kwargs):
        super().__init__(*args, **kwargs)
        self.telemetry_file = telemetry_file
        self.state_machine = create_server_state_machine()
        self.telementry = []
        
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            try:
                pdu = PDU.from_bytes(event.data)
                old_state, new_state = self.state_machine.on_pdu(pdu)
                print(f"Transitioned from {old_state} to {new_state} with PDU: {pdu}")
                
                if pdu.pdu_type == PDUType.AUTH_REQUEST:
                    self.send_auth_request(pdu)
                elif pdu.pdu_type == PDUType.TELEMETRY_REQUEST:
                    self.telementry.append(pdu.payload)
                elif pdu.pdu_type == PDUType.EMERGENCY:
                    print("Emergency PDU received, transitioning to TERMINATING state.")
                    self.send_terminate()
            except Exception as e:
                print(f"Error processing PDU: {e}")
        elif isinstance(event, ConnectionTerminated):
            self.dump_telemetry()
            
    def send_pdu(self, pdu):
        stream_id = 0
        self._quic.send_stream_data(stream_id, pdu.to_bytes(), end_stream=False)
        
    def send_auth_request(self, pdu):
        response = PDU(PDUType.AUTH_RESPONSE, version=1, session_id=pdu.session_id)
        self.send_pdu(response)
        self.state_machine.on_pdu(response)
        print("Sent AUTH_RESPONSE PDU")
    
    def send_terminate(self):
        pdu = PDU(PDUType.TERMINATE, version=1, session_id=0)
        self.send_pdu(pdu)
        self.state_machine.on_pdu(pdu)
        print("Sent TERMINATE PDU, transitioning to TERMINATED state.")
        
    def dump_telemetry(self):
        with open(self.telemetry_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            for payload in self.telementry:
                writer.writerow([payload])
                
async def main():
    configuration = QuicConfiguration(is_client=False)
    await serve(
        "0.0.0.0", 4433,
        configuration=configuration,
        create_protocol=lambda *args, **kwargs: WTCPServerProtocol(*args, telemetry_file="telemetry.csv", **kwargs)
    )
    
if __name__ == "__main__":
    asyncio.run(main())