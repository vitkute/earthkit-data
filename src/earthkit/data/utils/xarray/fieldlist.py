# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#


import logging
from collections import defaultdict

from earthkit.data.core.fieldlist import FieldList
from earthkit.data.core.index import Selection
from earthkit.data.core.index import normalize_selection
from earthkit.data.core.order import build_remapping

LOG = logging.getLogger(__name__)


class CollectorJoiner:
    def __init__(self, func):
        self.func = func

    def format_name(self, x, **kwargs):
        return self.func(x, **kwargs)

    def format_string(self, x):
        return str(x)

    def join(self, args):
        remapped = "".join(str(x) for x in args)
        components = tuple([str(x) for x in args[1::2]])
        return (remapped, components)

    @staticmethod
    def patch(patch, value):
        if isinstance(value, tuple) and len(value) == 2:
            return patch(value[0]), value[1]
        return patch(value)


class IndexSelection(Selection):
    def match_element(self, element):
        return all(v(element) for k, v in self.actions.items())


class IndexDB:
    def __init__(self, index, component):
        self._index = index if index is not None else dict()
        self._component = component if component is not None else dict()

    def index(self, key, maker=None):
        # LOG.debug(f"index(): {key=} {self._index=}")
        if key not in self._index:
            # # LOG.debug(f"Key={key} not found in IndexDB")
            if maker is not None:
                self._index[key] = maker(key)[key]
            else:
                raise KeyError(f"Could not find index for {key=}")
        return self._index[key]

    def component(self, key):
        if key not in self._component:
            raise KeyError(f"Could not find component for {key=}")
        return self._component[key]

    def collect(self, keys, component=False):
        remaining_keys = list(keys)
        indices = dict()
        components = dict()
        for k in keys:
            if k in self._index:
                indices[k] = self._index[k]
                remaining_keys.remove(k)
                if component and k in self._component:
                    components[k] = self._component[k]
        return remaining_keys, indices, components

    def filter(self, *args, **kwargs):
        kwargs = normalize_selection(*args, **kwargs)

        index = dict()
        component = dict()

        for k in self._index:
            if k in kwargs:
                selection = IndexSelection(dict(k=kwargs[k]))
                idx = list(i for i, element in enumerate(self._index[k]) if selection.match_element(element))
                index[k] = [self._index[k][i] for i in idx]
                if k in self._component:
                    component[k] = component[k][0], [self._component[k][1][i] for i in idx]
            else:
                index[k] = self._index[k]
                if k in self._component:
                    component[k] = self._component[k]
        return IndexDB(index, component)

    def __repr__(self) -> str:
        return f"IndexDB(_index={self._index}, component={self._component})"


class WrappedFieldList(FieldList):
    def __init__(self, fieldlist, keys=None, db=None, remapping=None):
        super().__init__()
        self.ds = fieldlist

        self.remapping = remapping
        if self.remapping is not None:
            self.remapping = build_remapping(remapping)

        self.db = IndexDB(None, None)
        if db is not None:
            self.db = db
        elif keys:
            self.db = IndexDB(*self.unique_values(keys, component=True))

        assert self.db

    def index(self, key, component=False):
        # print(f"called {key=}")
        if component:
            if self.remapping and key in self.remapping:
                return self.db.component(key)
            else:
                return None

        return self.db.index(key, self.unique_values)

    def __getitem__(self, n):
        return self.ds[n]

    def __len__(self):
        return len(self.ds)

    def sel(self, *args, **kwargs):
        assert "remapping" not in kwargs
        assert "patches" not in kwargs
        ds = self.ds.sel(*args, remapping=self.remapping, **kwargs)
        db = None
        # if not args and self.db and all(k in self.db for k in kwargs):
        #     db = self.db.filter(**kwargs)
        return WrappedFieldList(ds, db=db, remapping=self.remapping)

    def order_by(self, *args, **kwargs):
        assert "remapping" not in kwargs
        assert "patches" not in kwargs
        return WrappedFieldList(
            self.ds.order_by(*args, remapping=self.remapping, **kwargs), db=self.db, remapping=self.remapping
        )

    def unique_values(self, names, component=False):
        if isinstance(names, str):
            names = [names]

        keys, indices, components = self.db.collect(names, component=component)

        if keys:
            vals = defaultdict(dict)
            if component:
                components = dict()
                joiner = CollectorJoiner
            else:
                joiner = None

            for f in self.ds:
                r = f._attributes(keys, remapping=self.remapping, joiner=joiner)
                for k, v in r.items():
                    vals[k][v] = True

            vals = {k: tuple(values.keys()) for k, values in vals.items()}

            for k, v in vals.items():
                v = [x for x in v if x is not None]
                vals[k] = sorted(v)

            if component and self.remapping:
                for k, v in vals.items():
                    if k in self.remapping:
                        indices[k] = [x[0] for x in v]
                        components[k] = self.remapping.components(k), [x[1] for x in v]
                        assert len(indices[k]) == len(
                            components[k][1]
                        ), f"{len(indices[k])} != {len(components[k])} {indices[k]=} {components[k]=}"
                    else:
                        indices[k] = v
            else:
                for k, v in vals.items():
                    indices[k] = v

        if component:
            return indices, components
        else:
            return indices