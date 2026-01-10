"""
行为树模块

实现完整的行为树框架：
- 各种节点类型（Sequence, Selector, Condition, Action）
- 行为树解析和执行
- 行为树调试工具

根据 reference.md 第三阶段设计。
"""

from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import time

logger = logging.getLogger("BehaviorTree")


class NodeStatus(Enum):
    """节点状态"""

    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    IDLE = "idle"


@dataclass
class NodeContext:
    """节点执行上下文"""

    # 游戏状态
    game_state: Any = None

    # 玩家信息
    player_health: float = 1.0
    player_position: Tuple[float, float] = (0, 0)

    # 敌人信息
    enemies: List = field(default_factory=list)
    nearest_enemy: Any = None

    # 威胁信息
    threat_level: float = 0.0
    projectiles: List = field(default_factory=list)

    # 环境信息
    room_info: Any = None
    obstacles: List = field(default_factory=list)

    # 决策输出
    action: str = ""
    target: Any = None

    # 调试信息
    debug_info: Dict = field(default_factory=dict)


class BehaviorNode:
    """行为树节点基类"""

    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.parent: Optional["BehaviorNode"] = None
        self.children: List["BehaviorNode"] = []
        self.status: NodeStatus = NodeStatus.IDLE
        self.last_execution_time: float = 0
        self.execution_count: int = 0

        # 调试
        self.debug_enabled: bool = False

    def add_child(self, child: "BehaviorNode") -> "BehaviorNode":
        """添加子节点"""
        child.parent = self
        self.children.append(child)
        return child

    def execute(self, context: NodeContext) -> NodeStatus:
        """
        执行节点

        Args:
            context: 执行上下文

        Returns:
            节点状态
        """
        start_time = time.time()

        if self.debug_enabled:
            context.debug_info[self.name] = {
                "status": "running",
                "start_time": start_time,
            }

        try:
            result = self._execute(context)
            self.status = result
        except Exception as e:
            logger.error(f"Node {self.name} execution error: {e}")
            self.status = NodeStatus.FAILURE
            result = NodeStatus.FAILURE

        self.last_execution_time = time.time() - start_time
        self.execution_count += 1

        if self.debug_enabled:
            if self.name in context.debug_info:
                context.debug_info[self.name]["end_time"] = time.time()
                context.debug_info[self.name]["duration"] = self.last_execution_time
                context.debug_info[self.name]["result"] = result.value

        return result

    def _execute(self, context: NodeContext) -> NodeStatus:
        """子类实现的执行逻辑"""
        raise NotImplementedError

    def reset(self):
        """重置节点状态"""
        self.status = NodeStatus.IDLE
        for child in self.children:
            child.reset()

    def set_debug(self, enabled: bool):
        """设置调试模式"""
        self.debug_enabled = enabled
        for child in self.children:
            child.set_debug(enabled)


class SequenceNode(BehaviorNode):
    """顺序节点

    按顺序执行所有子节点。
    任何一个子节点失败，整个序列失败。
    所有子节点成功，序列成功。
    """

    def _execute(self, context: NodeContext) -> NodeStatus:
        # 如果正在运行，继续执行子节点
        for child in self.children:
            result = child.execute(context)

            if result == NodeStatus.FAILURE:
                return NodeStatus.FAILURE
            if result == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

        # 所有子节点成功
        return NodeStatus.SUCCESS


class SelectorNode(BehaviorNode):
    """选择节点

    按顺序尝试子节点。
    找到一个成功的就停止，返回成功。
    所有子节点都失败，返回失败。
    """

    def _execute(self, context: NodeContext) -> NodeStatus:
        for child in self.children:
            result = child.execute(context)

            if result == NodeStatus.SUCCESS:
                return NodeStatus.SUCCESS
            if result == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

        # 所有子节点都失败
        return NodeStatus.FAILURE


class ParallelNode(BehaviorNode):
    """并行节点

    同时执行所有子节点。
    """

    def __init__(self, name: str = None, policy: str = "all_success"):
        super().__init__(name)
        self.policy = policy  # "all_success", "any_success", "all_done"

    def _execute(self, context: NodeContext) -> NodeStatus:
        results = []

        for child in self.children:
            result = child.execute(context)
            results.append(result)

        if self.policy == "all_success":
            if all(r == NodeStatus.SUCCESS for r in results):
                return NodeStatus.SUCCESS
            elif any(r == NodeStatus.RUNNING for r in results):
                return NodeStatus.RUNNING
            else:
                return NodeStatus.FAILURE

        elif self.policy == "any_success":
            if any(r == NodeStatus.SUCCESS for r in results):
                return NodeStatus.SUCCESS
            elif any(r == NodeStatus.RUNNING for r in results):
                return NodeStatus.RUNNING
            else:
                return NodeStatus.FAILURE

        return NodeStatus.SUCCESS


class DecoratorNode(BehaviorNode):
    """装饰节点

    修改子节点的行为。
    """

    def __init__(self, name: str = None):
        super().__init__(name)
        self.child: Optional[BehaviorNode] = None

    def add_child(self, child: BehaviorNode) -> BehaviorNode:
        """装饰节点只接受一个子节点"""
        child.parent = self
        self.child = child
        self.children = [child]
        return child

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.child:
            return self.child.execute(context)
        return NodeStatus.FAILURE


class ConditionNode(BehaviorNode):
    """条件节点

    检查条件是否满足。
    """

    def __init__(
        self, name: str = None, condition: Callable[[NodeContext], bool] = None
    ):
        super().__init__(name)
        self.condition = condition

    def set_condition(self, condition: Callable[[NodeContext], bool]):
        """设置条件函数"""
        self.condition = condition

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.condition is None:
            return NodeStatus.SUCCESS

        try:
            if self.condition(context):
                return NodeStatus.SUCCESS
            else:
                return NodeStatus.FAILURE
        except Exception as e:
            logger.warning(f"Condition check error: {e}")
            return NodeStatus.FAILURE


class ActionNode(BehaviorNode):
    """动作节点

    执行具体动作。
    """

    def __init__(
        self, name: str = None, action: Callable[[NodeContext], NodeStatus] = None
    ):
        super().__init__(name)
        self.action = action

    def set_action(self, action: Callable[[NodeContext], NodeStatus]):
        """设置动作函数"""
        self.action = action

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.action is None:
            return NodeStatus.SUCCESS

        try:
            return self.action(context)
        except Exception as e:
            logger.warning(f"Action execution error: {e}")
            return NodeStatus.FAILURE


class InverterNode(DecoratorNode):
    """反转节点

    反转子节点的结果。
    """

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.child:
            result = self.child.execute(context)
            if result == NodeStatus.SUCCESS:
                return NodeStatus.FAILURE
            elif result == NodeStatus.FAILURE:
                return NodeStatus.SUCCESS
        return NodeStatus.RUNNING


class RepeaterNode(DecoratorNode):
    """重复节点

    重复执行子节点指定次数。
    """

    def __init__(self, name: str = None, repeat_count: int = 1):
        super().__init__(name)
        self.repeat_count = repeat_count
        self.current_repeat: int = 0

    def reset(self):
        super().reset()
        self.current_repeat = 0

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.child is None:
            return NodeStatus.SUCCESS

        while self.current_repeat < self.repeat_count:
            result = self.child.execute(context)

            if result == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            if result == NodeStatus.FAILURE:
                return NodeStatus.FAILURE

            self.current_repeat += 1

        return NodeStatus.SUCCESS


class CooldownNode(DecoratorNode):
    """冷却节点

    限制执行频率。
    """

    def __init__(self, name: str = None, cooldown_time: float = 1.0):
        super().__init__(name)
        self.cooldown_time = cooldown_time
        self.last_success_time: float = 0

    def reset(self):
        super().reset()
        self.last_success_time = 0

    def _execute(self, context: NodeContext) -> NodeStatus:
        current_time = time.time()

        if current_time - self.last_success_time < self.cooldown_time:
            return NodeStatus.FAILURE

        if self.child:
            result = self.child.execute(context)

            if result == NodeStatus.SUCCESS:
                self.last_success_time = current_time

            return result

        return NodeStatus.FAILURE


class BehaviorTree:
    """行为树

    管理行为树的执行。
    """

    def __init__(self, root: BehaviorNode = None):
        self.root = root or SelectorNode("Root")
        self.context = NodeContext()

        # 统计
        self.execution_count = 0
        self.total_execution_time = 0
        self.last_status: Optional[NodeStatus] = None

        # 调试
        self.debug_mode = False

    def set_root(self, root: BehaviorNode):
        """设置根节点"""
        self.root = root

    def execute(self, game_state: Any = None) -> NodeStatus:
        """
        执行行为树

        Args:
            game_state: 游戏状态

        Returns:
            根节点状态
        """
        # 更新上下文
        if game_state:
            self._update_context(game_state)

        start_time = time.time()

        # 执行根节点
        result = self.root.execute(self.context)

        self.last_status = result
        self.execution_count += 1
        self.total_execution_time += time.time() - start_time

        return result

    def _update_context(self, game_state: Any):
        """更新上下文"""
        # 从游戏状态提取信息
        # 这需要根据实际的游戏状态结构调整
        pass

    def reset(self):
        """重置行为树"""
        self.root.reset()
        self.context = NodeContext()

    def set_debug(self, enabled: bool):
        """设置调试模式"""
        self.debug_mode = enabled
        self.root.set_debug(enabled)

    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        avg_time = (
            self.total_execution_time / self.execution_count
            if self.execution_count > 0
            else 0
        )

        return {
            "execution_count": self.execution_count,
            "avg_execution_time": avg_time,
            "last_status": self.last_status.value if self.last_status else None,
            "root_name": self.root.name,
            "debug_info": self.context.debug_info if self.debug_mode else {},
        }

    def get_last_action(self) -> str:
        """获取最后执行的动作"""
        return self.context.action

    def get_target(self) -> Any:
        """获取最后选择的目标"""
        return self.context.target


# 预定义的行为树构建器
class CombatBehaviorTree:
    """战斗行为树构建器"""

    @staticmethod
    def create_combat_tree() -> BehaviorTree:
        """创建战斗行为树"""
        root = SelectorNode("CombatRoot")

        # 优先级1：紧急躲避
        dodge = SequenceNode("EmergencyDodge")
        dodge.add_child(
            ConditionNode(
                "HasProjectiles",
                lambda ctx: ctx.projectiles and len(ctx.projectiles) > 0,
            )
        )
        dodge_action = ActionNode("DodgeAction", CombatBehaviorTree._dodge_action)
        dodge.add_child(dodge_action)
        root.add_child(dodge)

        # 优先级2：低血量治疗
        heal = SequenceNode("LowHealthHeal")
        heal.add_child(ConditionNode("LowHealth", lambda ctx: ctx.player_health < 0.3))
        heal_action = ActionNode("HealAction", CombatBehaviorTree._heal_action)
        heal.add_child(heal_action)
        root.add_child(heal)

        # 优先级3：战斗逻辑
        combat = SequenceNode("Combat")
        combat.add_child(
            ConditionNode("InCombat", lambda ctx: ctx.enemies and len(ctx.enemies) > 0)
        )

        # 选择攻击目标
        select_target = ActionNode(
            "SelectTarget", CombatBehaviorTree._select_target_action
        )
        combat.add_child(select_target)

        # 执行攻击
        attack = ActionNode("Attack", CombatBehaviorTree._attack_action)
        combat.add_child(attack)

        root.add_child(combat)

        # 优先级4：移动到有利位置
        position = SequenceNode("Positioning")
        position.add_child(
            ConditionNode(
                "NotInCombat", lambda ctx: not ctx.enemies or len(ctx.enemies) == 0
            )
        )
        position_action = ActionNode(
            "PositioningAction", CombatBehaviorTree._positioning_action
        )
        position.add_child(position_action)
        root.add_child(position)

        return BehaviorTree(root)

    @staticmethod
    def _dodge_action(context: NodeContext) -> NodeStatus:
        """躲避动作"""
        # 躲避投射物
        context.action = "dodge"
        return NodeStatus.SUCCESS

    @staticmethod
    def _heal_action(context: NodeContext) -> NodeStatus:
        """治疗动作"""
        context.action = "heal"
        return NodeStatus.SUCCESS

    @staticmethod
    def _select_target_action(context: NodeContext) -> NodeStatus:
        """选择目标动作"""
        if context.enemies:
            # 选择最近的敌人
            context.target = min(context.enemies, key=lambda e: e.get("distance", 9999))
            context.action = "select_target"
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

    @staticmethod
    def _attack_action(context: NodeContext) -> NodeStatus:
        """攻击动作"""
        if context.target:
            context.action = "attack"
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

    @staticmethod
    def _positioning_action(context: NodeContext) -> NodeStatus:
        """走位动作"""
        context.action = "positioning"
        return NodeStatus.SUCCESS


class BehaviorTreeBuilder:
    """行为树构建器

    提供便捷的行为树构建方法。
    """

    def __init__(self):
        self._nodes: List[BehaviorNode] = []

    def selector(self, name: str = None) -> "BehaviorTreeBuilder":
        """创建选择节点"""
        node = SelectorNode(name)
        self._nodes.append(node)
        return self

    def sequence(self, name: str = None) -> "BehaviorTreeBuilder":
        """创建顺序节点"""
        node = SequenceNode(name)
        self._nodes.append(node)
        return self

    def condition(
        self, name: str = None, condition: Callable[[NodeContext], bool] = None
    ) -> "BehaviorTreeBuilder":
        """创建条件节点"""
        node = ConditionNode(name, condition)
        self._nodes.append(node)
        return node

    def action(
        self, name: str = None, action: Callable[[NodeContext], NodeStatus] = None
    ) -> "BehaviorTreeBuilder":
        """创建动作节点"""
        node = ActionNode(name, action)
        self._nodes.append(node)
        return node

    def invert(self, name: str = None) -> "BehaviorTreeBuilder":
        """创建反转节点"""
        node = InverterNode(name)
        self._nodes.append(node)
        return node

    def repeat(self, count: int, name: str = None) -> "BehaviorTreeBuilder":
        """创建重复节点"""
        node = RepeaterNode(name, count)
        self._nodes.append(node)
        return node

    def cooldown(self, seconds: float, name: str = None) -> "BehaviorTreeBuilder":
        """创建冷却节点"""
        node = CooldownNode(name, seconds)
        self._nodes.append(node)
        return node

    def build(self) -> BehaviorNode:
        """构建行为树（返回最后一个节点作为根）"""
        if not self._nodes:
            return SelectorNode("Empty")

        return self._nodes[-1]
