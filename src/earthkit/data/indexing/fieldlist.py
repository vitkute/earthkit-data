# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#


from earthkit.data.core.fieldlist import FieldList


class SimpleFieldList(FieldList):
    def __init__(self, fields=None):
        self.fields = fields if fields is not None else []

    def append(self, field):
        self.fields.append(field)

    def _getitem(self, n):
        return self.fields[n]

    def __len__(self):
        return len(self.fields)

    def __repr__(self) -> str:
        return f"FieldArray({len(self.fields)})"

    def __getstate__(self) -> dict:
        ret = {}
        ret["_fields"] = self.fields
        return ret

    def __setstate__(self, state: dict):
        self.fields = state.pop("_fields")

    def to_pandas(self, *args, **kwargs):
        # TODO make it generic
        if len(self) > 0:
            if self[0]._metadata.data_format() == "grib":
                from earthkit.data.readers.grib.pandas import PandasMixIn

                class _C(PandasMixIn, SimpleFieldList):
                    pass

                return _C(self.fields).to_pandas(*args, **kwargs)
        else:
            import pandas as pd

            return pd.DataFrame()

    def to_xarray(self, *args, **kwargs):
        # TODO make it generic
        if len(self) > 0:
            if self[0]._metadata.data_format() == "grib":
                from earthkit.data.readers.grib.xarray import XarrayMixIn

                class _C(XarrayMixIn, SimpleFieldList):
                    pass

                return _C(self.fields).to_xarray(*args, **kwargs)
        else:
            import xarray as xr

            return xr.Dataset()

    def mutate_source(self):
        return self

    @classmethod
    def new_mask_index(cls, *args, **kwargs):
        assert len(args) == 2
        fs = args[0]
        indices = list(args[1])
        return cls.from_fields([fs.fields[i] for i in indices])

    @classmethod
    def merge(cls, sources):
        if not all(isinstance(_, SimpleFieldList) for _ in sources):
            raise ValueError("SimpleFieldList can only be merged to another SimpleFieldLists")

        from itertools import chain

        return cls.from_fields(list(chain(*[f for f in sources])))


class WrappedField:
    def __init__(self, field):
        self._field = field

    def __getattr__(self, name):
        return getattr(self._field, name)

    def __repr__(self) -> str:
        return repr(self._field)


# class NewDataField(WrappedField):
#     def __init__(self, field, data):
#         super().__init__(field)
#         self._data = data
#         self.shape = data.shape

#     def to_numpy(self, flatten=False, dtype=None, index=None):
#         data = self._data
#         if dtype is not None:
#             data = data.astype(dtype)
#         if flatten:
#             data = data.flatten()
#         if index is not None:
#             data = data[index]
#         return data


class NewFieldMetadataWrapper:
    def __init__(self, field, **kwargs):
        from earthkit.data.core.metadata import WrappedMetadata

        self.__metadata = WrappedMetadata(field._metadata, extra=kwargs, owner=field)

    @property
    def _metadata(self):
        return self.__metadata


class NewFieldWrapper:
    def __init__(self, field, values=None, **kwargs):
        self._field = field
        self.__values = values

        if kwargs:
            from earthkit.data.core.metadata import WrappedMetadata

            self.__metadata = WrappedMetadata(field._metadata, extra=kwargs, owner=field)
        else:
            self.__metadata = field._metadata

    def _values(self, dtype=None):
        if self.__values is None:
            return self._field._values(dtype=dtype)
        else:
            if dtype is None:
                return self.__values
            return self.__values.astype(dtype)

    @property
    def _metadata(self):
        return self.__metadata

    def _has_new_values(self):
        return self.__values is not None


# For backwards compatibility
FieldArray = SimpleFieldList
