from netsquid import sim_run, qubits, b00
from netsquid.components import QuantumChannel, QSource, SourceStatus, FixedDelayModel, QuantumProcessor, \
    FibreDelayModel
from netsquid.nodes import Network, node
from netsquid.qubits import StateSampler

from src.network.PortPair import PortPair
from src.protocols.GenerateEntanglement import GenerateEntanglement


class StarNetwork:
    """
    Class to create a star network topology. The center of the network is composed of a Node with only a Quantum Source
    as a component. All the other nodes are composed by quantum processors, and are connected to the source node by
    means of quantum connections. One of the points of the stars is a repeater, which is connected to another node.


    Default network topology
    ------------------------
                 +-----+
                 | N1  |
                 +-----+
                    ^
                    |
                   QC1
                    |
    +----+        +---+        +---+        +-----+
    | N2 | <-QC2- | S | -QC4-> | R | <-QC5- | RN4 |
    +----+        +---+        +---+        +-----+
                    |
                   QC3
                    |
                    v
                 +-----+
                 | N3  |
                 +-----+


    Nodes
    -----
    S:
        - Quantum Source (generates |00> + |11>)

    R:
        - Quantum Processor
        - Quantum Memory (2x memory positions)

    Ni:
        - Quantum Processor
        - Quantum Memory (1x memory position)

    RNi:
        - Quantum Source (generates |00> + |11>)
        - Quantum Processor
        - Quantum Memory (1x memory position)


    Channels
    --------
    QCi:
        - Unidirectional Quantum Channel (S -> [Ni | R])

    QC5:
        - Unidirectional Quantum Channel (S <- RN)


    Network properties
    ------------------
    destinations_n (default: 5):
        The number of destination nodes in the network (one of which is a repeater)

    source_delay (default: 1e5):
        Delay of the delay model of the quantum source in nanoseconds

    channels_length (default: 10):
        The length of the quantum channels in km

    node_mem_positions (default: 1):
        The memory positions of the node's quantum memories

    repeater_mem_positions (default: 2):
        The memory positions of the repeater's quantum memory
    """
    _destinations_n: int = 5
    _source_delay: float = 1e5
    _channels_length: int = 10
    _node_mem_positions: int = 1
    _repeater_mem_positions: int = 2

    # Network object and network components
    _network: Network = Network("StarNetwork")

    _source: node = None
    _destinations: [node] = []

    _quantum_channels: [QuantumChannel] = []
    _quantum_channels_port_pairs: [PortPair] = []


    def __init__(self):
        """
        Constructor for the StarNetwork class.
        """
        self._init_source()
        self._init_destinations()
        self._init_quantum_channels()

        self._connect_remote_node()

    ###########
    # GETTERS #
    ###########

    @property
    def network(self) -> Network:
        """
        :type: Network
        """
        return self._network

    @property
    def source_delay(self) -> float:
        """
        :type: float
        """
        return self._source_delay

    @property
    def destinations_n(self) -> int:
        """
        :type: int
        """
        return self._destinations_n

    ###########
    # SETTERS #
    ###########

    @source_delay.setter
    def source_delay(self, ns: float):
        """
        Set the source delay in nanoseconds (ns).

        :param ns: The amount of nanoseconds
        :raise: AssertionError If ns is 0.0 or less
        """
        assert (ns >= 0.0)
        self._source_delay = ns

    @destinations_n.setter
    def destinations_n(self, n: int):
        """
        Set the number of destination nodes in the network.

        :param n: The number of nodes
        :raise: AssertionError If n is 0 or less
        """
        assert (n > 0)
        self._destinations_n = n

    #############################################
    # PRIVATE HELPERS USED TO BUILD THE NETWORK #
    #############################################

    def _init_source(self):
        """
        Initialize the source node of the network.
        """
        self._source = self._network.add_node("Source")
        self._source.add_subcomponent(
            # TODO: Change to `SourceStatus.INTERNAL` and add clock
            QSource("QuantumSource", state_sampler=StateSampler([b00]), status=SourceStatus.EXTERNAL,
                    models={"emission_delay_model": FixedDelayModel(delay=self._source_delay)}, num_ports=2)
        )

    def _init_destinations(self):
        """
        Initialize the destination nodes of the network.
        """
        for destination_n in range(1, self._destinations_n + 1):
            if destination_n == self._destinations_n - 1:
                # Initialization of the repeater
                self._destinations.append(self._network.add_node(f"Repeater"))
                self._destinations[destination_n - 1].add_subcomponent(
                    QuantumProcessor(f"QP_Repeater", num_positions=self._repeater_mem_positions,
                                     fallback_to_nonphysical=True)
                )
            elif destination_n == self._destinations_n:
                # Initialize the remote node
                self._destinations.append(self._network.add_node(f"RemoteNode"))
                self._destinations[destination_n - 1].add_subcomponent(
                    QuantumProcessor(f"QP_RemoteNode", num_positions=self._node_mem_positions,
                                     fallback_to_nonphysical=True)
                )
                self._destinations[destination_n - 1].add_subcomponent(
                    # TODO: Change to `SourceStatus.INTERNAL` and add clock
                    QSource("RemoteQuantumSource", state_sampler=StateSampler([b00]), status=SourceStatus.EXTERNAL,
                            models={"emission_delay_model": FixedDelayModel(delay=self._source_delay)}, num_ports=2)
                )
            else:
                # Initialize normal nodes
                self._destinations.append(self._network.add_node(f"Node{destination_n}"))
                self._destinations[destination_n - 1].add_subcomponent(
                    QuantumProcessor(f"QP_Node{destination_n}", num_positions=self._node_mem_positions,
                                     fallback_to_nonphysical=True)
                )

    def _init_quantum_channels(self):
        """
        Initialize the quantum channels of the network.
        """
        for (index, destination) in enumerate(self._destinations):
            if index == self._destinations_n - 2:
                # Initialize quantum channel for the repeater
                channel: QuantumChannel = QuantumChannel(f"QC_Source->Repeater", length=self._channels_length,
                                                         models={"delay_model": FibreDelayModel(c=200e3)})
                self._quantum_channels.append(channel)

                port_source, port_repeater = self.network.add_connection(self._source, destination, channel_to=channel,
                                                                         label=f"C_Source->Repeater")
                self._quantum_channels_port_pairs.append(PortPair(port_source, port_repeater))
            elif index == self._destinations_n - 1:
                # Initialize quantum channel for the remote node
                channel: QuantumChannel = QuantumChannel(f"QC_RemoteNode->Repeater", length=self._channels_length,
                                                         models={"delay_model": FibreDelayModel(c=200e3)})
                self._quantum_channels.append(channel)

                repeater = self._network.subcomponents["Repeater"]
                port_remote, port_repeater = self.network.add_connection(destination, repeater, channel_to=channel,
                                                                         label=f"C_RemoteNode->Repeater")
                self._quantum_channels_port_pairs.append(PortPair(port_remote, port_repeater))
            else:
                # Initialize quantum channels for normal nodes
                channel: QuantumChannel = QuantumChannel(f"QC_Source->Node{index}", length=self._channels_length,
                                                         models={"delay_model": FibreDelayModel(c=200e3)})
                self._quantum_channels.append(channel)

                port_source, port_destination = self.network.add_connection(self._source, destination,
                                                                            channel_to=channel,
                                                                            label=f"C_Source->Node{index + 1}")
                self._quantum_channels_port_pairs.append(PortPair(port_source, port_destination))

    def _connect_remote_node(self):
        repeater: node = self._destinations[-2]
        remote_node: node = self._destinations[-1]
        port_pair: PortPair = self._quantum_channels_port_pairs[-1]

        remote_node.subcomponents["RemoteQuantumSource"].ports["qout0"].forward_output(remote_node.ports[port_pair.source])
        remote_node.subcomponents["RemoteQuantumSource"].ports["qout1"].connect(remote_node.qmemory.ports["qin0"])

        repeater.ports[port_pair.destination].forward_input(repeater.qmemory.ports["qin1"])

    ###################################################################
    # PRIVATE METHODS TO CONNECT AND DISCONNECT DESTINATION NODE PORT #
    ###################################################################

    def _connect_source_to_destination(self, n: int):
        """
        Given the number of a node, connect it to the source's quantum source component.

        :param n: The number of the node to connect
        :raises: AssertionError If the index of the node is not in the range [1, self._destinations_n - 1]
        :raises: Exception If both of the ports are already connected to a node
        """
        assert (1 <= n <= self._destinations_n - 1)

        source: node = self._source
        destination: node = self._destinations[n - 1]
        port_pair: PortPair = self._quantum_channels_port_pairs[n - 1]
        source_ports: dict = source.subcomponents["QuantumSource"].ports

        # Check if both the ports are already connected to a node
        if len(source_ports["qout0"].forwarded_ports) != 0 and len(source_ports["qout1"].forwarded_ports) != 0:
            raise Exception("Two nodes have already been connected to the source's QuantumSource component")

        port_n = 0 if len(source_ports["qout0"].forwarded_ports) == 0 else 1

        source.subcomponents["QuantumSource"].ports[f"qout{port_n}"].forward_output(source.ports[port_pair.source])
        destination.ports[port_pair.destination].forward_input(destination.qmemory.ports["qin0"])

    def _disconnect_source_from_destination(self, n: int):
        """
        Given the number of a node, disconnect it from the source's quantum source component.

        :param n: The number of the node to disconnect
        :raises: AssertionError If the index of the node is not in the range [1, self._destinations_n - 1]
        :raises: Exception If the given node is not connected to the source's quantum source component
        """
        assert (1 <= n <= self._destinations_n - 1)

        ports: dict = self._source.subcomponents["QuantumSource"].ports
        q0: dict = ports["qout0"].forwarded_ports
        q1: dict = ports["qout1"].forwarded_ports

        # Look for the node n and disconnect it. If not found, raise an exception
        if len(q0) != 0 and (q0["output"].name == f"conn|{n}|C_Source->Node{n}"
                             or q0["output"].name == f"conn|{n}|C_Source->Repeater"):
            ports["qout0"].disconnect()
        elif len(q1) != 0 and (q1["output"].name == f"conn|{n}|C_Source->Node{n}"
                               or q1["output"].name == f"conn|{n}|C_Source->Repeater"):
            ports["qout1"].disconnect()
        else:
            raise Exception(f"The source node is not connected to Node {n}")

    ############################################
    # GENERATE ENTANGLEMENT BETWEEN NODE PAIRS #
    ############################################

    def entangle_nodes(self, node1: int, node2: int) -> dict:
        """
        Given two node indices, generate a bell pair and send one qubit to `node1` and one qubit to `node2`. The
        function then returns the two qubits and the fidelity of their entanglement compared to the entangled state
        `|00> + |11>`.

        :param node1: The index of the first node
        :param node2: The index of the second node
        :raises: AssertionError If the index of one of the nodes is either smaller than 0 or bigger than
                 `self._destinations_n` - 1
        :return: A dictionary containing the two qubits and the fidelity of their entanglement
        """
        assert (1 <= node1 <= self._destinations_n - 1 and 1 <= node2 <= self._destinations_n - 1)

        protocol_node1: GenerateEntanglement
        protocol_node2: GenerateEntanglement

        # Connect the source to the nodes
        self._connect_source_to_destination(node1)
        self._connect_source_to_destination(node2)

        # Initialize and start the protocols
        protocol_source: GenerateEntanglement = GenerateEntanglement(on_node=self._network.subcomponents["Source"],
                                                                     is_source=True, name="ProtocolSource")

        if node1 == self._destinations_n - 1 or node2 == self._destinations_n - 1:
            protocol_remote = GenerateEntanglement(on_node=self._network.subcomponents["RemoteNode"],
                                                   is_remote=True, name="ProtocolRemote")

            protocol_repeater = GenerateEntanglement(on_node=self._network.subcomponents["Repeater"],
                                                     is_repeater= True, name=f"ProtocolRepeater")

            if node1 == self._destinations_n - 1:
                protocol_node1 = protocol_repeater
                protocol_node2 = GenerateEntanglement(on_node=self._network.subcomponents[f"Node{node2}"],
                                                      name=f"ProtocolNode{node2}")
            elif node2 == self._destinations_n - 1:
                protocol_node1 = GenerateEntanglement(on_node=self._network.subcomponents[f"Node{node1}"],
                                                      name=f"ProtocolNode{node1}")
                protocol_node2 = protocol_repeater

            protocol_remote.start()
        else:
            protocol_node1 = GenerateEntanglement(on_node=self._network.subcomponents[f"Node{node1}"],
                                                  name=f"ProtocolNode{node1}")
            protocol_node2 = GenerateEntanglement(on_node=self._network.subcomponents[f"Node{node2}"],
                                                  name=f"ProtocolNode{node2}")

        protocol_source.start()
        protocol_node1.start()
        protocol_node2.start()

        # Run the simulation
        sim_run()

        # Disconnect the source from the nodes
        self._disconnect_source_from_destination(node1)
        self._disconnect_source_from_destination(node2)

        # Read the destination's memory
        # qubit_node1, = self._network.subcomponents[f"Node{node1}"].qmemory.peek(0)
        # qubit_node2, = self._network.subcomponents[f"Node{node2}"].qmemory.peek(0)
        # entanglement_fidelity: float = qubits.fidelity([qubit_node1, qubit_node2], b00)
        #
        # return {"qubits": (qubit_node1, qubit_node2), "fidelity": entanglement_fidelity}
