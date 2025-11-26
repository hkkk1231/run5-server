# Main Code 模块
"""
Main Code 模块，包含主要业务逻辑
"""

# 导入路径配置模块，使其可以通过 `from paths import ...` 访问
from . import paths
import sys
sys.modules['paths'] = paths

from . import spider