from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from struct import pack
from typing import Final

from .models import WyzeMeasurement, ensure_utc

FIT_EPOCH_OFFSET_SECONDS: Final[int] = 631065600
CRC_TABLE: Final[tuple[int, ...]] = (
    0x0000,
    0xCC01,
    0xD801,
    0x1400,
    0xF001,
    0x3C00,
    0x2800,
    0xE401,
    0xA001,
    0x6C00,
    0x7800,
    0xB401,
    0x5000,
    0x9C01,
    0x8801,
    0x4400,
)


@dataclass(frozen=True, slots=True)
class FitBaseType:
    field_type: int
    invalid_value: int
    size: int
    pack_format: str

    def encode(self, value: int | float | None, *, scale: int | None) -> bytes:
        if value is None:
            encoded_value: int | float = self.invalid_value
        elif scale is None:
            encoded_value = value
        else:
            encoded_value = int(round(value * scale))
        return pack(self.pack_format, encoded_value)


FIT_ENUM = FitBaseType(field_type=0x00, invalid_value=0xFF, size=1, pack_format="<B")
FIT_UINT8 = FitBaseType(field_type=0x02, invalid_value=0xFF, size=1, pack_format="<B")
FIT_UINT16 = FitBaseType(
    field_type=0x84, invalid_value=0xFFFF, size=2, pack_format="<H"
)
FIT_UINT32 = FitBaseType(
    field_type=0x86, invalid_value=0xFFFFFFFF, size=4, pack_format="<I"
)
FIT_UINT32Z = FitBaseType(
    field_type=0x8C, invalid_value=0x00000000, size=4, pack_format="<I"
)


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    number: int
    base_type: FitBaseType
    value: int | float | None
    scale: int | None = None


class WeightScaleFitEncoder:
    HEADER_SIZE: Final[int] = 12
    FILE_TYPE_WEIGHT: Final[int] = 9
    MESSAGE_FILE_ID: Final[int] = 0
    MESSAGE_DEVICE_INFO: Final[int] = 23
    MESSAGE_WEIGHT_SCALE: Final[int] = 30
    MESSAGE_FILE_CREATOR: Final[int] = 49
    LMSG_FILE_ID: Final[int] = 0
    LMSG_FILE_CREATOR: Final[int] = 1
    LMSG_DEVICE_INFO: Final[int] = 2
    LMSG_WEIGHT_SCALE: Final[int] = 3

    def __init__(self) -> None:
        self._buffer = BytesIO()
        self._write_header(data_size=0)
        self._device_info_defined = False
        self._weight_scale_defined = False

    def build(self, measurement: WyzeMeasurement) -> bytes:
        timestamp = _fit_timestamp(measurement.measured_at)
        self._write_file_id(time_created=timestamp)
        self._write_file_creator()
        self._write_device_info(timestamp=timestamp)
        self._write_weight_scale(measurement=measurement, timestamp=timestamp)
        self._finish()
        return self._buffer.getvalue()

    def _write_header(self, *, data_size: int) -> None:
        self._buffer.seek(0)
        self._buffer.write(
            pack("<BBHI4s", self.HEADER_SIZE, 16, 108, data_size, b".FIT")
        )

    def _write_definition(
        self, *, local_message: int, global_message: int, fields: list[FieldDefinition]
    ) -> None:
        self._buffer.write(self._record_header(local_message, is_definition=True))
        self._buffer.write(pack("<BBHB", 0, 0, global_message, len(fields)))
        for field in fields:
            self._buffer.write(
                pack(
                    "<BBB",
                    field.number,
                    field.base_type.size,
                    field.base_type.field_type,
                )
            )

    def _write_record(
        self, *, local_message: int, fields: list[FieldDefinition]
    ) -> None:
        self._buffer.write(self._record_header(local_message, is_definition=False))
        for field in fields:
            self._buffer.write(field.base_type.encode(field.value, scale=field.scale))

    def _write_file_id(self, *, time_created: int) -> None:
        fields = [
            FieldDefinition(3, FIT_UINT32Z, 1),
            FieldDefinition(4, FIT_UINT32, time_created),
            FieldDefinition(1, FIT_UINT16, 11),
            FieldDefinition(2, FIT_UINT16, 2429),
            FieldDefinition(5, FIT_UINT16, 1),
            FieldDefinition(0, FIT_ENUM, self.FILE_TYPE_WEIGHT),
        ]
        self._write_definition(
            local_message=self.LMSG_FILE_ID,
            global_message=self.MESSAGE_FILE_ID,
            fields=fields,
        )
        self._write_record(local_message=self.LMSG_FILE_ID, fields=fields)

    def _write_file_creator(self) -> None:
        fields = [
            FieldDefinition(0, FIT_UINT16, None),
            FieldDefinition(1, FIT_UINT8, None),
        ]
        self._write_definition(
            local_message=self.LMSG_FILE_CREATOR,
            global_message=self.MESSAGE_FILE_CREATOR,
            fields=fields,
        )
        self._write_record(local_message=self.LMSG_FILE_CREATOR, fields=fields)

    def _write_device_info(self, *, timestamp: int) -> None:
        fields = [
            FieldDefinition(253, FIT_UINT32, timestamp),
            FieldDefinition(3, FIT_UINT32Z, 1),
            FieldDefinition(7, FIT_UINT32, 1),
            FieldDefinition(8, FIT_UINT32, None),
            FieldDefinition(2, FIT_UINT16, 11),
            FieldDefinition(4, FIT_UINT16, 2429),
            FieldDefinition(5, FIT_UINT16, 1, scale=100),
            FieldDefinition(10, FIT_UINT16, 1, scale=256),
            FieldDefinition(0, FIT_UINT8, 1),
            FieldDefinition(1, FIT_UINT8, 119),
            FieldDefinition(6, FIT_UINT8, 1),
            FieldDefinition(11, FIT_UINT8, 1),
        ]
        if not self._device_info_defined:
            self._write_definition(
                local_message=self.LMSG_DEVICE_INFO,
                global_message=self.MESSAGE_DEVICE_INFO,
                fields=fields,
            )
            self._device_info_defined = True
        self._write_record(local_message=self.LMSG_DEVICE_INFO, fields=fields)

    def _write_weight_scale(
        self, *, measurement: WyzeMeasurement, timestamp: int
    ) -> None:
        fields = [
            FieldDefinition(253, FIT_UINT32, timestamp),
            FieldDefinition(0, FIT_UINT16, measurement.weight_kg, scale=100),
            FieldDefinition(1, FIT_UINT16, measurement.percent_fat, scale=100),
            FieldDefinition(2, FIT_UINT16, measurement.percent_hydration, scale=100),
            FieldDefinition(3, FIT_UINT16, measurement.visceral_fat_mass, scale=100),
            FieldDefinition(4, FIT_UINT16, measurement.bone_mass_kg, scale=100),
            FieldDefinition(5, FIT_UINT16, measurement.muscle_mass_kg, scale=100),
            FieldDefinition(7, FIT_UINT16, measurement.basal_met, scale=4),
            FieldDefinition(9, FIT_UINT16, measurement.active_met, scale=4),
            FieldDefinition(8, FIT_UINT8, measurement.physique_rating),
            FieldDefinition(10, FIT_UINT8, measurement.metabolic_age),
            FieldDefinition(11, FIT_UINT8, measurement.visceral_fat_rating),
            FieldDefinition(13, FIT_UINT16, measurement.bmi, scale=10),
        ]
        if not self._weight_scale_defined:
            self._write_definition(
                local_message=self.LMSG_WEIGHT_SCALE,
                global_message=self.MESSAGE_WEIGHT_SCALE,
                fields=fields,
            )
            self._weight_scale_defined = True
        self._write_record(local_message=self.LMSG_WEIGHT_SCALE, fields=fields)

    @staticmethod
    def _record_header(local_message: int, *, is_definition: bool) -> bytes:
        header = local_message
        if is_definition:
            header |= 1 << 6
        return pack("<B", header)

    def _finish(self) -> None:
        data_size = self._size() - self.HEADER_SIZE
        self._write_header(data_size=data_size)
        self._buffer.seek(0, 2)
        self._buffer.write(pack("<H", _crc16(self._buffer.getvalue())))

    def _size(self) -> int:
        current_pos = self._buffer.tell()
        self._buffer.seek(0, 2)
        size = self._buffer.tell()
        self._buffer.seek(current_pos)
        return size


def build_fit_file(measurement: WyzeMeasurement) -> bytes:
    return WeightScaleFitEncoder().build(measurement)


def _fit_timestamp(value: datetime) -> int:
    measured_at = ensure_utc(value)
    return int(measured_at.timestamp()) - FIT_EPOCH_OFFSET_SECONDS


def _crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc = _update_crc(crc, byte)
    return crc


def _update_crc(current_crc: int, byte: int) -> int:
    tmp = CRC_TABLE[current_crc & 0xF]
    crc = ((current_crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[byte & 0xF]
    tmp = CRC_TABLE[crc & 0xF]
    return ((crc >> 4) & 0x0FFF) ^ tmp ^ CRC_TABLE[(byte >> 4) & 0xF]
