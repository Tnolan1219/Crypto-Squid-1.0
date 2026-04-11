"""
Crypto Squid 1.0 (legacy snapshot).

This module preserves the pre-v3 parameter set by re-exporting the v2 baseline
that was running before the 3.0 upgrade.
"""

from params_v2 import BTC_V2 as BTC_1_0
from params_v2 import ETH_V2 as ETH_1_0
from params_v2 import DEFAULT_V2_PARAMS as DEFAULT_1_0_PARAMS
from params_v2 import SymbolParamsV2 as SymbolParams1_0
from params_v2 import V2Params as Params1_0
