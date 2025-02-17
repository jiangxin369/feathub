# Copyright 2022 The FeatHub Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from abc import ABC
from collections import OrderedDict
from copy import deepcopy
from typing import Optional, List, Union, cast, Sequence, Dict

from feathub.dsl.expr_parser import ExprParser

from feathub.common.exceptions import FeathubException
from feathub.common.types import DType
from feathub.feature_views.feature import Feature
from feathub.feature_views.transforms.expression_transform import ExpressionTransform
from feathub.feature_views.transforms.join_transform import JoinTransform
from feathub.feature_views.transforms.over_window_transform import OverWindowTransform
from feathub.feature_views.transforms.sliding_window_transform import (
    SlidingWindowTransform,
)
from feathub.table.table_descriptor import TableDescriptor

feathub_expr_parser = ExprParser()


class FeatureView(TableDescriptor, ABC):
    """
    Provides metadata to derive a table of feature values from other tables.
    """

    def __init__(
        self,
        name: str,
        source: Union[str, TableDescriptor],
        features: Sequence[Union[str, Feature]],
        keep_source_fields: bool = False,
        timestamp_field: Optional[str] = None,
        timestamp_format: str = "epoch",
    ):
        """
        :param name: The unique identifier of this feature view in the registry.
        :param source: The source dataset used to derive this feature view. If it is a
                       string, it should refer to the name of a table descriptor in the
                       registry.
        :param features: A list of features to be joined onto this feature view.
                         If a feature is a string, it should be either in the format
                         {table_name}.{feature_name}, which refers to a feature in the
                         table with the given name, or in the format {feature_name},
                         which refers to a feature in the source table.
        :param keep_source_fields: True iff all fields in the source table should be
                                   included in this table. The feature in the source
                                   will be overwritten by the feature in this feature
                                   view if they have the same name.
        :param timestamp_field: Optional. If not None, the feature with the given name
                                is used as the `timestamp_field` of the TableDescriptor
                                represented by this FeatureView. Otherwise, the
                                `timestamp_field` of the source TableDescriptor is used
                                as the `timestamp_field` of the TableDescriptor
                                represented by this FeatureView.
        :param timestamp_format: The format of the timestamp field. This argument only
                                 takes effect when the `timestamp_field` is not None.
                                 Otherwise, the `timestamp_format` of the source
                                 TableDescriptor is used as the `timestamp_format` of
                                 the TableDescriptor represented by this FeatureView.
        """

        self.source = source
        self.features = features
        self.keep_source_fields = keep_source_fields

        is_unresolved = self.is_unresolved()
        keys = None if is_unresolved else self._get_keys()
        super().__init__(
            name=name,
            keys=keys,
            timestamp_field=timestamp_field,
            timestamp_format=timestamp_format,
        )

        if not is_unresolved:
            # Uses table's keys as features' keys if features' keys are not specified.
            for feature in [f for f in self.get_resolved_features() if f.keys is None]:
                feature.keys = keys

            for feature in [f for f in self.get_resolved_features() if f.dtype is None]:
                variable_types = self._get_variable_types()
                feature.dtype = self._derive_feature_dtype(feature, variable_types)

            if self.timestamp_field is None:
                self.timestamp_field = self.get_resolved_source().timestamp_field
                self.timestamp_format = self.get_resolved_source().timestamp_format

            feature_names = set()
            for feature in self.get_resolved_features():
                if feature.name in feature_names:
                    raise FeathubException(
                        f"FeatureView {name} contains duplicated feature name "
                        f"{feature.name}."
                    )
                feature_names.add(feature.name)

    def is_unresolved(self) -> bool:
        return (
            isinstance(self.source, str)
            or (isinstance(self.source, FeatureView) and self.source.is_unresolved())
            or any(isinstance(f, str) for f in self.features)
        )

    # TODO: Remove this method and add a method to OnDemandFeatureView to get output
    #  features with source fields.
    def get_output_fields(self, source_fields: List[str]) -> List[str]:
        """
        Returns the names of fields of this table descriptor. This method should be
        called after the FeatureView is resolved, otherwise exception will be raised.
        The output fields include:
        - All fields in the source_fields if keep_source_fields is True.
        - The timestamp field if it is not None.
        - All features and features' keys.

        :param source_fields: The names of fields of the source table.
        :return: The names of fields of this table descriptor.
        """
        if self.is_unresolved():
            raise FeathubException(
                "Build this feature view before getting output fields."
            )
        output_fields = []
        if self.keep_source_fields:
            output_fields.extend(source_fields)
        elif self.timestamp_field is not None:
            output_fields.append(self.timestamp_field)

        for feature in self.get_resolved_features():
            if feature.keys is not None:
                output_fields.extend(feature.keys)
            output_fields.append(feature.name)

        # Order output fields similar to their order in the source table.
        reordered_output_fields = []
        for field in source_fields:
            if field in output_fields:
                reordered_output_fields.append(field)
        reordered_output_fields.extend(output_fields)

        return list(OrderedDict.fromkeys(reordered_output_fields))

    def get_output_features(self) -> List[Feature]:
        if self.is_unresolved():
            raise RuntimeError("Build this feature view before getting features.")

        source_features = self.get_resolved_source().get_output_features()
        features = {
            **{f.name: f for f in source_features},
            **{f.name: f for f in self.get_resolved_features()},
        }

        output_feature_names = self.get_output_fields([f.name for f in source_features])
        output_features = []
        for feature_name in output_feature_names:
            output_features.append(features[feature_name])

        return output_features

    def get_resolved_features(self) -> Sequence[Feature]:
        if self.is_unresolved():
            raise RuntimeError("This feature view is unresolved.")
        return cast(Sequence[Feature], self.features)

    def get_resolved_source(self) -> TableDescriptor:
        if self.is_unresolved():
            raise RuntimeError("This feature view is unresolved.")
        return cast(TableDescriptor, self.source)

    def _get_keys(self) -> Optional[List[str]]:
        if self.keep_source_fields and cast(TableDescriptor, self.source).keys is None:
            return None

        feature_with_keys = [
            f for f in self.get_resolved_features() if f.keys is not None
        ]
        # Table's keys are unknown if no feature has keys specified.
        if not self.keep_source_fields and not feature_with_keys:
            return None

        key_fields: List[str] = []
        if self.keep_source_fields:
            keys: Sequence[str] = cast(TableDescriptor, self.source).keys
            if keys is not None:
                key_fields.extend(keys)
        for feature in feature_with_keys:
            keys = feature.keys
            if keys is not None:
                key_fields.extend(keys)

        return list(OrderedDict.fromkeys(key_fields))

    def is_bounded(self) -> bool:
        return self.get_resolved_source().is_bounded()

    def get_bounded_view(self) -> TableDescriptor:
        if self.is_bounded():
            return self

        feature_view = deepcopy(self)
        feature_view.source = self.get_resolved_source().get_bounded_view()
        return feature_view

    def _get_variable_types(self) -> Dict[str, DType]:
        variable_types = {
            **{feature.name: feature.dtype for feature in self.get_output_features()},
            **{
                feature.name: feature.dtype
                for feature in self.get_resolved_source().get_output_features()
            },
        }
        return variable_types

    def _derive_feature_dtype(
        self, feature: Feature, variable_types: Dict[str, DType]
    ) -> Optional[DType]:
        transform = feature.transform
        if isinstance(transform, ExpressionTransform):
            dtype = feathub_expr_parser.parse(transform.expr).eval_dtype(variable_types)
        elif isinstance(transform, OverWindowTransform) or isinstance(
            transform, SlidingWindowTransform
        ):
            expr_result_type = feathub_expr_parser.parse(transform.expr).eval_dtype(
                variable_types
            )
            dtype = transform.agg_func.get_result_type(expr_result_type)
        elif isinstance(transform, JoinTransform):
            raise FeathubException("JoinTransform feature should have dtype set.")
        else:
            raise FeathubException(
                f"Cannot derive feature data type of {type(transform)} feature"
            )

        variable_types[feature.name] = dtype
        return dtype
