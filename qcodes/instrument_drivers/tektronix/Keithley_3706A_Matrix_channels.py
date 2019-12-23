import logging
import struct
import numpy as np
import warnings
import time
import itertools
from typing import List, Dict, Optional, Union

import qcodes as qc
from qcodes import VisaInstrument, DataSet
from qcodes.instrument.channel import InstrumentChannel
from qcodes.instrument.base import Instrument, Parameter
from qcodes.instrument.parameter import ArrayParameter, ParameterWithSetpoints
import qcodes.utils.validators as vals
from qcodes.utils.helpers import create_on_off_val_mapping


class KeithleyMatrixChannel(InstrumentChannel):
    """
    """

    def __init__(self, parent: Instrument, name: str, channel: str) -> None:
        """
        """
        super().__init__(parent, name)


class Keithley_3706A(VisaInstrument):
    """
    """

    def __init__(self, name: str, address: str, **kwargs) -> None:
        """
        Args:
            name: Name to use internally in QCoDeS
            address: VISA resource address
        """
        super().__init__(name, address, terminator='\n', **kwargs)

        self.channels: List[KeithleyMatrixChannel] = []

        self.add_parameter('gpib_enable',
                           get_cmd=self._get_gpib_status,
                           set_cmd=self._set_gpib_status,
                           val_mapping=create_on_off_val_mapping(on_val='true',
                                                                 off_val='false'
                                                                 ))

        self.add_parameter('gpib_address',
                           get_cmd=self._get_gpib_address,
                           get_parser=int,
                           set_cmd=self._set_gpib_address,
                           vals=vals.Ints(1, 30))

        self.add_parameter('lan_enable',
                           get_cmd=self._get_lan_status,
                           set_cmd=self._set_lan_status,
                           val_mapping=create_on_off_val_mapping(on_val='true',
                                                                 off_val='false'
                                                                 ))

        self.connect_message()

    def _get_channels(self) -> List[str]:
        """
        """
        cards = self.get_switch_cards()

        slot_id = []
        for _, item in enumerate(cards):
            slot_id.append('{slot_no}'.format(**item))

        total_number_of_rows = [int(float(self.ask(
            f'slot[{int(i)}].rows.matrix'))) for i in slot_id]

        total_number_of_columns = [int(float(self.ask(
            f'slot[{int(i)}].columns.matrix'))) for i in slot_id]

        row_list = []
        for _, item in enumerate(total_number_of_rows):
            rows_in_each_slot = [str(i) for i in range(1, item+1)]
            row_list.append(rows_in_each_slot)

        column_list = []
        for _, item in enumerate(total_number_of_columns):
            columns_in_each_slot = []
            for i in range(1, item+1):
                if i < 10:
                    columns_in_each_slot.append('0'+str(i))
                else:
                    columns_in_each_slot.append(str(i))
            column_list.append(columns_in_each_slot)

        matrix_channels = []
        for i, slot in enumerate(slot_id):
            for element in itertools.product(slot, row_list[i], column_list[i]):
                matrix_channels.append(''.join(element))
        return matrix_channels

    def _get_gpib_status(self) -> str:
        return self.ask('comm.gpib.enable')

    def _set_gpib_status(self, val: Union[str, bool]) -> None:
        self.write(f'comm.gpib.enable = {val}')

    def _get_lan_status(self) -> str:
        return self.ask('comm.lan.enable')

    def _set_lan_status(self, val: Union[str, bool]) -> None:
        self.write(f'comm.lan.enable = {val}')

    def _get_gpib_address(self) -> int:
        return int(float(self.ask('gpib.address')))

    def _set_gpib_address(self, val: int) -> None:
        self.write(f'gpib.address = {val}')

    def get_idn(self) -> Dict[str, Optional[str]]:
        idnstr = self.ask_raw('*IDN?')
        vendor, model, serial, firmware = map(str.strip, idnstr.split(','))
        model = model[6:]

        idn: Dict[str, Optional[str]] = {'vendor': vendor, 'model': model,
                                         'serial': serial, 'firmware': firmware}
        return idn

    def get_switch_cards(self) -> List[Dict[str, Optional[str]]]:
        switch_cards: List[Dict[str, Optional[str]]] = []
        for i in range(1, 7):
            scard = self.ask(f'slot[{i}].idn')
            if scard != 'Empty Slot':
                model, mtype, firmware, serial = map(str.strip,
                                                     scard.split(','))
                sdict = {'slot_no': i, 'model': model, 'mtype': mtype,
                         'firmware': firmware, 'serial': serial}
                switch_cards.append(sdict)
        return switch_cards

    def get_available_memory(self) -> Dict[str, Optional[str]]:
        memstring = self.ask('memory.available()')
        systemMemory, scriptMemory, \
            patternMemory, configMemory = map(str.strip, memstring.split(','))

        memory_available: Dict[str, Optional[str]] = {
            'System Memory  (%)': systemMemory,
            'Script Memory  (%)': scriptMemory,
            'Pattern Memory (%)': patternMemory,
            'Config Memory  (%)': configMemory
        }
        return memory_available

    def get_ip_address(self) -> str:
        return self.ask('lan.status.ipaddress')

    def reset_local_network(self) -> None:
        self.write('lan.reset()')

    def save_setup(self, val: Optional[str] = None) -> None:
        if val is not None:
            self.write(f'setup.save({val})')
        else:
            self.write(f'setup.save()')

    def load_setup(self, val: Union[int, str]):
        self.write(f'setup.recall({val})')

    def connect_message(self) -> None:
        """
        """
        idn = self.get_idn()
        cards = self.get_switch_cards()

        con_msg = ('Connected to: {vendor} {model} SYSTEM SWITCH '
                   '(serial:{serial}, firmware:{firmware})'.format(**idn))
        print(con_msg)
        self.log.info(f"Connected to instrument: {idn}")

        for _, item in enumerate(cards):
            card_info = ('Slot {slot_no}- Model:{model}, Matrix Type:{mtype}, '
                         'Firmware:{firmware}, Serial:{serial}'.format(**item))
            print(card_info)
            self.log.info(f'Switch Cards: {item}')

    def ask(self, cmd: str) -> str:
        """
        Override of normal ask. This is important, since queries to the
        instrument must be wrapped in 'print()'
        """
        return super().ask('print({:s})'.format(cmd))
