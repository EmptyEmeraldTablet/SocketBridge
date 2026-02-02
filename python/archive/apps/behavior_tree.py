"""
SocketBridge 行为树模块

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
        """执行节点"""
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

        return NodeStatus.SUCCESS


class SelectorNode(BehaviorNode):
    """选择节点

    按顺序执行子节点，返回第一个成功的子节点的结果。
    所有子节点都失败，序列失败。
    """

    def _execute(self, context: NodeContext) -> NodeStatus:
        for child in self.children:
            result = child.execute(context)

            if result == NodeStatus.SUCCESS:
                return NodeStatus.SUCCESS
            if result == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

        return NodeStatus.FAILURE


class ParallelNode(BehaviorNode):
    """并行节点

    同时执行所有子节点。
    可以配置为：全部成功、一半成功、任一成功等策略。
    """

    def __init__(
        self,
        name: str = None,
        policy: str = "all_success",
    ):
        super().__init__(name)
        self.policy = policy  # "all_success", "one_success", "majority"

    def _execute(self, context: NodeContext) -> NodeStatus:
        results = []
        for child in self.children:
            result = child.execute(context)
            results.append(result)

        if self.policy == "all_success":
            if all(r == NodeStatus.SUCCESS for r in results):
                return NodeStatus.SUCCESS
            if any(r == NodeStatus.RUNNING for r in results):
                return NodeStatus.RUNNING
            return NodeStatus.FAILURE

        elif self.policy == "one_success":
            if any(r == NodeStatus.SUCCESS for r in results):
                return NodeStatus.SUCCESS
            if any(r == NodeStatus.RUNNING for r in results):
                return NodeStatus.RUNNING
            return NodeStatus.FAILURE

        elif self.policy == "majority":
            success_count = sum(1 for r in results if r == NodeStatus.SUCCESS)
            if success_count > len(results) // 2:
                return NodeStatus.SUCCESS
            if any(r == NodeStatus.RUNNING for r in results):
                return NodeStatus.RUNNING
            return NodeStatus.FAILURE

        return NodeStatus.FAILURE


class ConditionNode(BehaviorNode):
    """条件节点

    检查某个条件是否满足。
    满足返回成功，不满足返回失败。
    """

    def __init__(
        self,
        name: str = None,
        condition: Callable[[NodeContext], bool] = None,
    ):
        super().__init__(name)
        self.condition = condition

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.condition is None:
            return NodeStatus.SUCCESS

        try:
            if self.condition(context):
                return NodeStatus.SUCCESS
            return NodeStatus.FAILURE
        except Exception as e:
            logger.error(f"Condition check error: {e}")
            return NodeStatus.FAILURE


class ActionNode(BehaviorNode):
    """动作节点

    执行某个动作。
    总是返回成功（除非出错）。
    """

    def __init__(
        self,
        name: str = None,
        action: Callable[[NodeContext], NodeStatus] = None,
    ):
        super().__init__(name)
        self.action = action

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.action is None:
            return NodeStatus.SUCCESS

        try:
            result = self.action(context)
            return result
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return NodeStatus.FAILURE


class DecoratorNode(BehaviorNode):
    """装饰节点

    修改子节点的执行行为。
    """

    def __init__(self, name: str = None):
        super().__init__(name)
        self.child: Optional[BehaviorNode] = None

    def set_child(self, child: BehaviorNode) -> "DecoratorNode":
        """设置子节点"""
        child.parent = self
        self.child = child
        self.children = [child]
        return self

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.child is None:
            return NodeStatus.FAILURE
        return self.child.execute(context)


class NotDecorator(DecoratorNode):
    """取反装饰器"""

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.child is None:
            return NodeStatus.FAILURE

        result = self.child.execute(context)

        if result == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        elif result == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        return result


class RepeatDecorator(DecoratorNode):
    """重复装饰器"""

    def __init__(self, name: str = None, times: int = 1):
        super().__init__(name)
        self.times = times
        self.current_count = 0

    def reset(self):
        super().reset()
        self.current_count = 0

    def _execute(self, context: NodeContext) -> NodeStatus:
        if self.child is None:
            return NodeStatus.FAILURE

        self.current_count = 0

        while self.current_count < self.times:
            result = self.child.execute(context)
            self.current_count += 1

            if result == NodeStatus.FAILURE:
                return NodeStatus.FAILURE
            if result == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

        return NodeStatus.SUCCESS


class BehaviorTree:
    """行为树"""

    def __init__(self, root: BehaviorNode = None):
        self.root = root
        self.context = NodeContext()

    def execute(self) -> NodeStatus:
        """执行行为树"""
        if self.root is None:
            return NodeStatus.FAILURE

        # 重置所有节点
        self.root.reset()
        self.context = NodeContext()

        # 执行根节点
        return self.root.execute(self.context)

    def update(self) -> NodeStatus:
        """更新行为树（用于持续执行）"""
        if self.root is None:
            return NodeStatus.FAILURE

        return self.root.execute(self.context)

    def set_debug(self, enabled: bool):
        """设置调试模式"""
        if self.root:
            self.root.set_debug(enabled)

    def get_last_action(self) -> str:
        """获取最后执行的动作"""
        return self.context.action

    def get_debug_info(self) -> Dict:
        """获取调试信息"""
        return dict(self.context.debug_info)


class BehaviorTreeBuilder:
    """行为树构建器

    提供流式 API 构建行为树。
    """

    def __init__(self):
        self.root: Optional[BehaviorNode] = None
        self.current: BehaviorNode = None

    def selector(self, name: str = None) -> "BehaviorTreeBuilder":
        """创建选择节点"""
        node = SelectorNode(name)
        self._add_node(node)
        return self

    def sequence(self, name: str = None) -> "BehaviorTreeBuilder":
        """创建顺序节点"""
        node = SequenceNode(name)
        self._add_node(node)
        return self

    def parallel(
        self, name: str = None, policy: str = "all_success"
    ) -> "BehaviorTreeBuilder":
        """创建并行节点"""
        node = ParallelNode(name, policy)
        self._add_node(node)
        return self

    def condition(
        self,
        name: str = None,
        condition: Callable[[NodeContext], bool] = None,
    ) -> "BehaviorTreeBuilder":
        """创建条件节点"""
        node = ConditionNode(name, condition)
        self._add_node(node)
        return self

    def action(
        self,
        name: str = None,
        action: Callable[[NodeContext], NodeStatus] = None,
    ) -> "BehaviorTreeBuilder":
        """创建动作节点"""
        node = ActionNode(name, action)
        self._add_node(node)
        return self

    def not_(self, name: str = None) -> "BehaviorTreeBuilder":
        """创建取反装饰器"""
        node = NotDecorator(name)
        self._add_node(node)
        return self

    def repeat(self, times: int = 1, name: str = None) -> "BehaviorTreeBuilder":
        """创建重复装饰器"""
        node = RepeatDecorator(name, times)
        self._add_node(node)
        return self

    def end(self) -> "BehaviorTreeBuilder":
        """返回父节点"""
        if self.current and self.current.parent:
            self.current = self.current.parent
        return self

    def build(self) -> BehaviorTree:
        """构建行为树"""
        if self.root is None:
            raise ValueError("No nodes added to behavior tree")

        return BehaviorTree(self.root)

    def _add_node(self, node: BehaviorNode):
        """添加节点到树中"""
        if self.root is None:
            self.root = node
            self.current = node
        elif self.current:
            self.current.add_child(node)
            # 如果是复合节点（Selector, Sequence, Parallel），进入该节点
            if isinstance(
                node,
                (SelectorNode, SequenceNode, ParallelNode, DecoratorNode),
            ):
                self.current = node


def create_combat_behavior_tree() -> BehaviorTree:
    """创建战斗行为树"""
    builder = BehaviorTreeBuilder()

    # 根选择节点
    builder.selector("CombatRoot")

    # 优先级1: 躲避投射物
    builder.sequence("DodgeProjectiles")
    builder.condition("HasProjectiles", lambda ctx: len(ctx.projectiles) > 0)
    builder.action("DodgeAction", lambda ctx: NodeStatus.SUCCESS)
    builder.end()  # 返回选择节点

    # 优先级2: 低血量治疗
    builder.sequence("HealPriority")
    builder.condition("LowHealth", lambda ctx: ctx.player_health < 0.3)
    builder.condition("CanHeal", lambda ctx: ctx.player_health < 0.5)
    builder.action("HealAction", lambda ctx: NodeStatus.SUCCESS)
    builder.end()  # 返回选择节点

    # 优先级3: 战斗逻辑
    builder.sequence("Combat")
    builder.condition("HasEnemies", lambda ctx: len(ctx.enemies) > 0)
    builder.selector("CombatActions")
    builder.action("Attack", lambda ctx: NodeStatus.SUCCESS)  # TODO: 实现攻击逻辑
    builder.action("MoveToEnemy", lambda ctx: NodeStatus.SUCCESS)  # TODO: 实现移动逻辑
    builder.end()  # 返回选择节点
    builder.end()  # 返回选择节点

    # 优先级4: 移动到有利位置
    builder.sequence("Positioning")
    builder.condition("ShouldReposition", lambda ctx: ctx.threat_level > 0.5)
    builder.action("Reposition", lambda ctx: NodeStatus.SUCCESS)  # TODO: 实现走位逻辑
    builder.end()  # 返回选择节点

    return builder.build()
