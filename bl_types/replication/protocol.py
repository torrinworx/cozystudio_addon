class ReplicatedDatablock(object):
    """
    Datablock translation definition to handle DCC<->Replication data exchange.
    """
    # Type parameters
    is_root = False
    use_delta = False

    @staticmethod
    def construct(data: dict) -> object:
        """
        Create a new datablock of the corresponding instance according to the
        given data dtype entry.

        :param data: data dumped according to the dump() definition
        :type data: dict
        :return: datablock instance
        """
        raise NotImplementedError()

    @staticmethod
    def dump(datablock: object) -> dict:
        """
        Extract the given datablock instance data into a dict.

        :param datablock: datablock instance
        :type datablock: datablock type
        :return: dict
        """
        raise NotImplementedError()

    @staticmethod
    def load(data: dict, datablock: object):
        """
        Load extracted data into the given datablock.

        :param data: data dumped according to the dump() implementation
        :type data: dict
        :param datablock: datablock instance
        :type datablock: datablock type
        """
        raise NotImplementedError()

    @staticmethod
    def resolve(data: dict) -> object:
        """
        Find a corresponding datablock instance according to the given data

        :param datablock: datablock instance
        :type datablock: datablock type
        :return: datablock instance
        """
        raise NotImplementedError()

    @staticmethod
    def resolve_deps(datablock: object) -> [object]:
        """
        Get all dependencies of the given datablock.

        :param datablock: datablock instance
        :type datablock: datablock type
        :return: list() of datablock dependencies
        """
        raise NotImplementedError()

    @staticmethod
    def needs_update(datablock: object, data:dict)-> bool:
        """
        Fastcheck to test if a the latest commited state of the datablock
         is outdated.

        :param datablock: datablock instance
        :type datablock: datablock type
        :param data: node data in its last committed state
        :type data: dict
        """
        return True

    # TODO: Add back once we figure out how to get pip packages into blender add-on dev env
    # @staticmethod
    # def compute_delta(last_data:dict, current_data: dict)-> Delta:
    #     """
    #     Compute the node delta between current_state and last committed state

    #     :param last_data: last committed data
    #     :type last_data: dict
    #     :param current_data: current datablock state
    #     :type current_data: dict
    #     :return: deepdiff.Delta
    #     """
    #     return Delta(DeepDiff(last_data, current_data, cache_size=5000))


class DataTranslationProtocol(object):
    """
    A simple protocol to handle programs data translation between a program
    and replication based on a given ReplicatedDatablock implementations.
    # TODO: validate implementations
    # TODO: tests implementations
    # TODO: version implementation/protocol
    """

    def __init__(self):
        self._supported_types = {}

    def register_implementation(
            self,
            dcc_types,
            implementation):
        """
        Register a new replicated datatype implementation
        """

        if type(dcc_types) is list:
            for dcc_type in dcc_types:
                self._supported_types[dcc_type.__name__] = implementation
                # logging.debug(f"Registering DCC type {dcc_type.__name__}")
        else:
            self._supported_types[dcc_types.__name__] = implementation
            # logging.debug(f"Registering DCC type {dcc_types.__name__}")

    def construct(self, data: dict) -> object:
        """
        Create a new datablock of the corresponding instance according to the
        given data type_id entry.

        :param data: data dumped according to the dump() implementation
        :type data: dict
        :return: datablock instance
        """
        type_id = data.get('type_id')
        return self._supported_types.get(type_id).construct(data)

    def dump(self, datablock: object, stamp_uuid: str=None) -> dict:
        """
        Extract the given datablock instance data into a dict.

        :param datablock: datablock instance
        :type datablock: datablock type
        :return: dict
        """
        type_id = type(datablock).__name__

        data = self._supported_types.get(type_id).dump(datablock)

        # stamp with type id
        data['type_id'] = type_id
        if stamp_uuid:
            data['uuid'] = stamp_uuid

        return data

    def load(self, data: dict, datablock: object):
        """
        Load extracted data into the given datablock.

        :param data: data dumped according to the dump() implementation
        :type data: dict
        :param datablock: datablock instance
        :type datablock: datablock type
        """
        type_id = data.get('type_id')
        self._supported_types.get(type_id).load(data, datablock)

    def resolve(self, data: dict) -> object:
        """
        Find a corresponding datablock instance according to the given data

        :param datablock: datablock instance
        :type datablock: datablock type
        :return: datablock instance
        """
        type_id = data.get('type_id')
        return self._supported_types.get(type_id).resolve(data)

    def resolve_deps(self, datablock: object) -> [object]:
        """
        Get all dependencies of the given datablock.

        :param datablock: datablock instance
        :type datablock: datablock type
        :return: list() of datablock dependencies
        """
        type_id = type(datablock).__name__
        return self._supported_types.get(type_id).resolve_deps(datablock)

    def needs_update(self, datablock: object, data:dict)-> bool:
        """
        Fastcheck to test if a the latest commited state of the datablock
         is outdated.

        :param datablock: datablock instance
        :type datablock: datablock type
        :param data: node data in its last committed state
        :type
        """
        type_id = type(datablock).__name__
        return self._supported_types[type_id].needs_update(datablock, data)

    def get_implementation(self, datablock) -> ReplicatedDatablock:
        """Retrieve a registered implementation
        """
        if isinstance(datablock, str):
            type_id = datablock
        else:
            type_id = type(datablock).__name__

        return self._supported_types.get(type_id)

    @property
    def implementations(self) -> dict:
        """ Get a dict containing the protocol registered implementations
        """
        return self._supported_types

    # TODO: Add back once we figure out how to get pip packages into blender add-on dev env
    # def compute_delta(self, last_data:dict, current_data: dict)-> Delta:
    #     """
    #     Compute the node delta between current_state and last committed state

    #     :param last_data: last committed data
    #     :type last_data: dict
    #     :param current_data: current datablock state
    #     :type current_data: dict
    #     :return: deepdiff.Delta
    #     """
    #     type_id = current_data.get('type_id')
    #     return self._supported_types.get(type_id).compute_delta(last_data, current_data)
