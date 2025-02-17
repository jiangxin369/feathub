#  Copyright 2022 The FeatHub Authors
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import unittest
from typing import cast

from feathub.common.config import flatten_dict
from feathub.registries.local_registry import LocalRegistry
from feathub.registries.registry import Registry


class RegistryTest(unittest.TestCase):
    def test_instantiate(self):
        config = flatten_dict(
            {
                "registry": {
                    "type": "local",
                    "local": {"namespace": "my-namespace"},
                }
            }
        )
        registry = Registry.instantiate(props=config)
        self.assertIsInstance(registry, LocalRegistry)
        self.assertEqual("my-namespace", cast(LocalRegistry, registry).namespace)
