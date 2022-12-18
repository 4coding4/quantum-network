import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from numpy import ndarray
from tqdm import tqdm

from src.network.StarNetwork import StarNetwork


class Experiment:
    """
    Class to set up and perform experiments on the network.


    Experiment properties
    ---------------------
    num_each_simulation (default 100):
        The number of runs to perform for each step of the simulation

    csv_path (default "./out/data.csv")
        The path of the csv file

    fig_path (default "./out/fidelity-over-length.png")
        The path of the figure generated by the experiment

    """
    _num_each_simulation: int = 100
    _csv_path: str = "../out/data.csv"
    _lengths: ndarray = np.arange(10, 1000 + 10, 10)
    _fig_path: str = "../out/fidelity-over-length.png"

    _verbose: bool = False
    _network: StarNetwork = None


    def __init__(self, network: StarNetwork, verbose=False):
        """
        Constructor for the Experiment class.

        :param network: The StarNetwork to experiment on
        :param verbose: If the class needs to print more info
        """
        self._network = network
        self._verbose = verbose

    ###########
    # GETTERS #
    ###########

    @property
    def num_each_simulation(self) -> int:
        """
        :type: int
        """
        return self._num_each_simulation

    @property
    def csv_path(self) -> str:
        """
        :type: str
        """
        return self._csv_path

    @property
    def fig_path(self) -> str:
        """
        :type: str
        """
        return self._fig_path

    ###########
    # SETTERS #
    ###########

    @num_each_simulation.setter
    def num_each_simulation(self, value: int):
        """
        Set the number of measurements for each run of the simulation.
        
        :param value: The number of measurements for each run of the simulation
        :raises AssertionError: If the value is smaller than 0 
        """
        assert (value > 0)
        self._num_each_simulation = value

    @csv_path.setter
    def csv_path(self, filename: str):
        """
        Set the filename for the csv file.

        :param filename: The name of the file
        :raises AssertionError: If the filename does not contain the .csv extension
        """
        # assert (".csv" not in filename)
        self._csv_path = filename

    @fig_path.setter
    def fig_path(self, filename: str):
        """
        Set the filename for the png file.

        :param filename: The name of the file
        :raises AssertionError: If the filename does not contain the .png extension
        """
        # assert (".png" not in filename)
        self._fig_path = filename

    ############################################
    # FUNCTIONS USED TO PERFORM THE EXPERIMENT #
    ############################################

    def run(self, node1: int, node2: int):
        """
        Run the simulation between the two given nodes. When the simulation is over, a

        :param node1: The index of the first node
        :param node2: The index of the second node
        """
        f = open(self._csv_path, "w+")
        f.write(f"length,fidelity,not-decoherence\r\n")

        for length in tqdm(self._lengths):
            fidelity_values = []
            self._network.channels_length = length

            if self._verbose:
                print(f"Nodes are entangled after {self._network.channels_length * 1000} meters")

            for i in range(self._num_each_simulation):
                try:
                    result_dict = self._network.entangle_nodes(node1, node2)
                    fidelity_values.append(result_dict["fidelity"])
                except KeyError:
                    fidelity_values.append(0)

                    if self._verbose:
                        print("Either one or both Qubits were lost during transfer")

            if self._verbose:
                print(f"fidelity values: {fidelity_values}")
                print(f"Average fidelity: {np.mean(fidelity_values)}")
                print(f"Number of not decoherence qubits: {(np.array(fidelity_values) > 0.5).sum()}")

            f.write(f"{length},{np.mean(fidelity_values)},{(np.array(fidelity_values) > 0.5).sum()}\r\n")

        f.close()
        self._plot_results()

    def _plot_results(self):
        dataframe = pd.read_csv(self._csv_path)
        a, b = np.polyfit(dataframe["length"], dataframe["fidelity"], 1)

        fig = plt.figure(figsize=(20, 10))
        plt.title("Fidelity of entanglement over distance")
        plt.plot(dataframe["length"], dataframe["fidelity"], 'o')
        plt.plot(dataframe["length"], a * dataframe["length"] + b)
        plt.xlabel("Length of quantum channel (m)")
        plt.ylabel("Fidelity")
        plt.xscale("linear")
        plt.yscale("linear")
        plt.show()

        fig.savefig(self._fig_path)
