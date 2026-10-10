# -*- coding: utf-8 -*-
"""`game/application/` —— 应用流程层（承《代码层机制模块化架构方案》§1 目标树、§6-1 依赖方向）。

定位：位于「前端/API/Backend」与「core 业务机制」之间，负责**跨机制的流程编排**
（回合生命周期、记忆协调等），不拥有业务规则，也不持有第二份账本。

依赖方向（§6-1）：`backend/UI → application → core.workflows.evaluation / core.save_load / memory`。
允许的唯一反向边是**兼容门面**：`core.commands.finish_turn` 薄代理到这里（§5.2）。
两条禁令，勿增勿破：
  ① `application` **不得** import `core.commands`——否则门面与服务层互引成新环；
  ② `core/` 下除该门面外的业务模块**不得** import `application`——生命周期归应用层，
     不由业务域暗中兼管（§6-2）。

按 §6-6「公共接口小而稳」：本文件不做通配 re-export，调用方显式 import 具体模块。
"""
