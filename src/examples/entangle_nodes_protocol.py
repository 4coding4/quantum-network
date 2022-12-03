import netsquid.qubits.ketstates as ketstates
from netsquid import sim_run, qubits, b00
from netsquid.components import QuantumProcessor, QSource, SourceStatus, FixedDelayModel, QuantumChannel, Port
from netsquid.nodes import Network, node
from netsquid.protocols.nodeprotocols import NodeProtocol
from netsquid.protocols.protocol import Signals
from netsquid.qubits import StateSampler
from src.errors.FibreErrorModel import FibreErrorModel
from src.errors.T1T2ErrorModel import T1T2ErrorModel

PROCESS_POSITIONS: int = 3
SOURCE_MODEL_DELAY: int = 5
QUANTUM_CHANNEL_DELAY: int = 100


class EntangleNodes(NodeProtocol):
    """
    Cooperate with another node to generate shared entanglement.
    """
    _is_source: bool = False
    _qsource_name: node = None
    _input_mem_position: int = 0
    _qmem_input_port: Port = None

    def __init__(self, on_node: node, is_source: bool, name: str, input_mem_pos: int = 1) -> None:
        """
        Constructor for the EntangleNode protocol class.

        :param on_node: Node to run this protocol on
        :param is_source: Whether this protocol should act as a source or a receiver. Both are needed
        :param name: Name of the protocol
        :param input_mem_pos: Index of quantum memory position to expect incoming qubits on. Default is 0
        """
        super().__init__(node=on_node, name=name)

        self._is_source = is_source

        if not self._is_source:
            self._input_mem_position = input_mem_pos
            self._qmem_input_port = self.node.qmemory.ports[f"qin{self._input_mem_position}"]
            self.node.qmemory.mem_positions[self._input_mem_position].in_use = True

    def run(self) -> None:
        """
        Send entangled qubits of the source and destination nodes.
        """
        if self._is_source:
            self.node.subcomponents[self._qsource_name].trigger()
        else:
            yield self.await_port_input(self._qmem_input_port)
            self.send_signal(Signals.SUCCESS, self._input_mem_position)

    @property
    def is_connected(self) -> bool:
        if self._is_source:
            for name, subcomp in self.node.subcomponents.items():
                if isinstance(subcomp, QSource):
                    self._qsource_name = name
                    break
            else:
                return False

        return True


def network_setup() -> Network:
    """
    This function creates and returns a quantum network.


    Nodes
    -----
    Alice:
        - Quantum Processor
            - qin0: Connected to Quantum Source
        - Quantum Source
            - qout0: Forwards output to Quantum Channel
            - qout1: Connected to Quantum Memory

    Bob:
        - Quantum Processor
            - qin0: input from Quantum Channel is forwarded to Quantum Memory


    Channels
    --------
    QuantumChannel:
        - From: Alice
        - To: Bob


    Diagram
    -------
    +---------------------+                                      +---------------------+
    |                     | +----------------------------------+ |                     |
    | "NodeAlice:"        | |                                  | | "NodeBob:"          |
    | "QSource"           O-* "Connection: QuantumChannel -->" *-O "QuantumProcessor"  |
    | "QuantumProcessor"  | |                                  | |                     |
    |                     | +----------------------------------+ |                     |
    +---------------------+                                      +---------------------+


    :return: The assembled quantum network
    """

    # Create a quantum network and add the nodes Alice and Bob
    network: Network = Network("Entangle_nodes")
    alice: node = network.add_node("Alice")
    bob: node = network.add_node("Bob")

    # Add a Quantum Processor to each node in the network. The Quantum Processor is a quantum memory which is able to
    # execute quantum programs or instructions. The parameter `num_positions` indicates the number of available memory
    # positions should the processor have.
    alice.add_subcomponent(
        QuantumProcessor("QuantumMemoryAlice", num_positions=PROCESS_POSITIONS, fallback_to_nonphysical=True)
    )
    bob.add_subcomponent(
        QuantumProcessor("QuantumMemoryBob", num_positions=PROCESS_POSITIONS, fallback_to_nonphysical=True)
    )

    # Add a component that generates Qubits. The qubits generated by the component share a specified quantum state. The
    # generated qubits have state b00, this means `|00> + |11>`. Moreover, the source will distribute the generated qubits
    # over 2 ports, and the quantum source will generate pulses when its input ports are triggered. Finally, the `Fixed
    # Delay Model` is the model used to compute the time it takes to generate the pulse. Only one pulse can be handled
    # at a time.
    alice.add_subcomponent(
        QSource("QuantumSourceAlice", state_sampler=StateSampler([ketstates.b00]), num_ports=2,
                status=SourceStatus.EXTERNAL, models={"emission_delay_model": FixedDelayModel(delay=5)})
    )

    # Create a dictionary of models for the models parameter of QuantumChannel
    models = dict(quantum_loss_model=FibreErrorModel.fibre_loss_model,
                  quantum_noise_model=T1T2ErrorModel.t1t2_noise_model)

    # Create a quantum channel and add the connection to the network. The connection is made between nodes Alice and
    # Bob. The quantum channel is placed from Alice to Bob.
    quantum_channel: QuantumChannel = QuantumChannel("QuantumChannel", delay=100, models=models)
    port_alice, port_bob = network.add_connection(alice, bob, channel_to=quantum_channel, label="quantum")

    # Set up ports in Alice's nodes. The method `forward_output` when called on a port forwards the value of that port
    # to another port – namely the port of the quantum connection. The second port of the quantum source component is
    # connected to the input of the quantum memory of the node.
    alice.subcomponents["QuantumSourceAlice"].ports["qout0"].forward_output(alice.ports[port_alice])
    alice.subcomponents["QuantumSourceAlice"].ports["qout1"].connect(alice.qmemory.ports["qin0"])

    # Set up the port in Bob's node. The quantum channel's port forwards the input to the input port of the quantum
    # memory of the node.
    bob.ports[port_bob].forward_input(bob.qmemory.ports["qin0"])

    return network


if __name__ == '__main__':
    qnetwork: Network = network_setup()

    protocol_alice = EntangleNodes(on_node=qnetwork.subcomponents["Alice"], is_source=True, name="ProtocolAlice")
    protocol_bob = EntangleNodes(on_node=qnetwork.subcomponents["Bob"], is_source=False, name="ProtocolBob")

    protocol_alice.start()
    protocol_bob.start()

    sim_run()

    try:
        q1, = qnetwork.subcomponents["Alice"].qmemory.peek(0)
        q2, = qnetwork.subcomponents["Bob"].qmemory.peek(0)

        # Compute the fidelity between the qubits quantum state and the reference state (`|00> + |11>`)
        print(f"Fidelity of generated entanglement: {qubits.fidelity([q1, q2], b00)}")
    except:
        # If one or more of the qubits are dead, display the memories
        print("Current situation of the qubits: (Alice, Bob)")
        print(qnetwork.subcomponents["Alice"].qmemory.peek(0))
        print(qnetwork.subcomponents["Bob"].qmemory.peek(0))

