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
from typing import List, Dict, Any

from feathub.common.config import ConfigDef
from feathub.processors.processor_config import ProcessorConfig, PROCESSOR_PREFIX

SPARK_PROCESSOR_PREFIX = PROCESSOR_PREFIX + "spark."

MASTER_CONFIG = SPARK_PROCESSOR_PREFIX + "master"
MASTER_DOC = "The Spark master URL to connect to."

NATIVE_CONFIG_PREFIX = SPARK_PROCESSOR_PREFIX + "native."

# TODO: Add a validator class that are used to validate the legality of
#  configuration values, and validate that spark master is not None.
spark_processor_config_defs: List[ConfigDef] = [
    ConfigDef(
        name=MASTER_CONFIG,
        value_type=str,
        description=MASTER_DOC,
    ),
]


class SparkProcessorConfig(ProcessorConfig):
    def __init__(self, props: Dict[str, Any]) -> None:
        super().__init__(props)
        self.update_config_values(spark_processor_config_defs)
