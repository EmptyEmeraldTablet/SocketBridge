# 快速参考卡片

## 快速命令

```bash
# 启动
python run.py              # 交互模式
python run.py --ai         # AI模式
python run.py --basic      # 桥接模式
python run.py --test       # 运行测试
python run.py --status     # 检查状态

# 直接启动
python isaac_bridge.py
python orchestrator_enhanced.py
python example_ai.py
```

---

## 导入速查

```python
# 完整导入
from socketbridge import *

# 基础
from socketbridge import SimpleAI, IsaacBridge

# 高级
from socketbridge import EnhancedCombatOrchestrator, AIConfig
```

---

## 核心类

| 类 | 用途 |
|---|---|
| `IsaacBridge` | 游戏通信 |
| `SimpleAI` | 简单AI |
| `EnhancedCombatOrchestrator` | 完整AI |
| `AIConfig` | AI配置 |
| `CombatOrchestrator` | 原始主控 |

---

## 配置模板

```python
from socketbridge import EnhancedCombatOrchestrator, AIConfig

config = AIConfig(
    attack_aggression=0.7,     # 0-1
    defense_preference=0.5,    # 0-1
    movement_style="kiting",   # kiting/aggressive/defensive
    enable_behavior_tree=True,
    enable_advanced_control=True,
    enable_adaptive_behavior=True,
)

orchestrator = EnhancedCombatOrchestrator(config)
orchestrator.initialize()
```

---

## 状态枚举

```python
# 战斗状态
CombatState.IDLE        # 空闲
CombatState.EXPLORING   # 探索
CombatState.COMBAT      # 战斗
CombatState.EVASION     # 闪避
CombatState.RETREATING  # 撤退
CombatState.HEALING     # 治疗

# 策略
StrategyType.AGGRESSIVE  # 激进
StrategyType.DEFENSIVE   # 防御
StrategyType.BALANCED    # 平衡
StrategyType.EVASIVE     # 闪避
StrategyType.HEALING     # 治疗

# 威胁
ThreatLevel.LOW      # 低
ThreatLevel.MEDIUM   # 中
ThreatLevel.HIGH     # 高
ThreatLevel.CRITICAL # 紧急
```

---

## 完整示例

```python
from socketbridge import IsaacBridge, SimpleAI

bridge = IsaacBridge()
ai = SimpleAI(use_enhanced=True)
ai.connect()

@bridge.on("data")
def handle_data(data):
    move, shoot = ai.update(data)
    bridge.send_input(move=move, shoot=shoot)

bridge.start()
```

---

## 文件位置

```
SocketBridge/
├── python/
│   ├── run.py              ← 启动器
│   ├── isaac_bridge.py     ← 核心
│   ├── orchestrator_enhanced.py  ← AI
│   └── test_integration.py ← 测试
└── docs/
    ├── QUICKSTART.md       ← 入门
    ├── SYSTEM_DOCUMENTATION.md  ← 完整文档
    ├── TROUBLESHOOTING.md  ← 问题解决
    └── API_QUICK_REFERENCE.md   ← API参考
```

---

**参考**: [完整文档](SYSTEM_DOCUMENTATION.md)
