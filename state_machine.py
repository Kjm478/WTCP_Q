from enum import Enum, auto
from pdu import PDUType

class ClientState(Enum):
    INITIAL = auto()
    AUTH_PENDING = auto()
    OPERATIONAL = auto()
    TERMINATING = auto()
    TERMINATED = auto()
    
    
    
class ServerState(Enum):
    LISTENING = auto()
    AUTHORIZING = auto()
    OPERATIONAL = auto()
    TERMINATING = auto()
    TERMINATED = auto()
    
class StateMachineError(Exception):
    """Exception Raised for invalid state transitions."""
    pass

class StateMachine:
    """state machine for WTCP-Q client and server.
       handles transitions based on current state and incoming PDU types.
        
    """
    
    def __init__(self, initial_state, transitions):
        
        self.state = initial_state
        self._transitions = transitions
        
    def on_pdu(self, pdu): 
        """
        process an incoming PDU and transition state if valid.
        """
        key = (self.state, pdu.pdu_type)
        if key in self._transitions:
            old_state = self.state
            self.state = self._transitions[key]
            
            return old_state, self.state
        else: 
            raise StateMachineError(f"Invalid transition from {self.state} with PDU type {pdu.pdu_type}")
        

# client transitions: (current_state, received_pdu) -> next_state
CLIENT_TRANSITIONS = {
    (ClientState.INITIAL, PDUType.AUTH_REQUEST): ClientState.AUTH_PENDING,
    (ClientState.AUTH_PENDING, PDUType.AUTH_RESPONSE): ClientState.OPERATIONAL,
    (ClientState.OPERATIONAL, PDUType.CONTROL): ClientState.OPERATIONAL,
    (ClientState.OPERATIONAL, PDUType.EMERGENCY): ClientState.TERMINATING,
    (ClientState.OPERATIONAL, PDUType.TERMINATE): ClientState.TERMINATING,
    (ClientState.TERMINATING, PDUType.TERMINATE): ClientState.TERMINATED,
}

# server transitions: (current_state, received_pdu) -> next_state
SERVER_TRANSITIONS = {
    (ServerState.LISTENING, PDUType.AUTH_REQUEST): ServerState.AUTHORIZING,
    (ServerState.AUTHORIZING, PDUType.AUTH_RESPONSE): ServerState.OPERATIONAL,
    (ServerState.AUTHORIZING, PDUType.TELEMETRY_REQUEST): ServerState.OPERATIONAL,
    (ServerState.OPERATIONAL, PDUType.TELEMETRY_REQUEST): ServerState.OPERATIONAL,
    (ServerState.OPERATIONAL, PDUType.EMERGENCY): ServerState.TERMINATING,
    (ServerState.OPERATIONAL, PDUType.TERMINATE): ServerState.TERMINATED,
    (ServerState.TERMINATING, PDUType.TERMINATE): ServerState.TERMINATED,
}

def create_client_state_machine():
    """Create a state machine for the WTCP-Q client."""
    return StateMachine(ClientState.INITIAL, CLIENT_TRANSITIONS)

def create_server_state_machine():
    """Create a state machine for the WTCP-Q server."""
    return StateMachine(ServerState.LISTENING, SERVER_TRANSITIONS)