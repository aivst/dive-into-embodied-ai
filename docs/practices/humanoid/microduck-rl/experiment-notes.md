---
title: "MicroDuck：实验记录与创意动作"
sidebar_position: 99
displayed_sidebar: practicesHumanoidSidebar
---

# 实验记录与创意动作

这里保留教程素材的来源、历史实验结果与未进入主线的创意探索。初次学习请从[MicroDuck 动手教程](./index.md)开始。以下为已有实验记录，本次页面改版未重新运行这些训练。

## 如何理解这些记录

checkpoint 可以加载、能够生成回放，与任务成功是不同层次。短片中的表现也不能直接外推到多 seed、其他地形或真实硬件。历史记录中的18个模式回放不代表18种动作均通过完成度验收。

<details>
<summary>查看历史跨模式训练指标</summary>

![部分模式的训练指标汇总](./figs/microduck-matrix-summary.webp)

图中只包含能从 TensorBoard 汇总出的指标。跨任务奖励定义不同，不能仅用奖励数值横向比较动作质量。

</details>

## 验收记录：三个主展示动作

本轮按实际 mjlab 的固定条件回放重新筛选主展示动作。最终使用轮式起身、轮式转向和踢球：动作过程清楚，素材经过近距离裁切，踢球片段还截去了后续重置画面。

| 动作 | 说明 | 固定条件验收 | GIF | MP4 |
| --- | --- | --- | --- | --- |
| RollerStandUp | 从趴地状态起身并站稳 | 起身后保持站立；初始趴地帧单独计入筛查 | [播放](./figs/focus-final/roller_standup_final.gif) | [下载](./figs/focus-final/roller_standup_final.mp4) |
| Velocity-Swizzle | 轮式转向 | `0/150` 疑似倒地帧；最低躯干高度 0.0975 m；直立度最低 0.9887 | [播放](./figs/focus-final/roller_swizzle_final.gif) | [下载](./figs/focus-final/roller_swizzle_final.mp4) |
| BallKick-Flat | 踢球并收势 | `0/120` 疑似倒地帧；最低躯干高度 0.0955 m；直立度最低 0.7072 | [播放](./figs/focus-final/ballkick_final.gif) | [下载](./figs/focus-final/ballkick_final.mp4) |

三段视频和完整验收字段见 [`figs/focus-final/evaluation.tsv`](./figs/focus-final/evaluation.tsv)。统一验收方式是实际 mjlab 环境、固定 seed 42、单环境、50 Hz；`fell_like` 只用于筛查画面中的明显失稳，不能替代多 seed 或真机测试。

原先集中训练的 `StandUp-Flat`、`GroundPick-Flat` 仍保留在训练脚本和实验日志中。当前复核显示 StandUp 中间姿态不连贯，GroundPick 微调后仍停在低伏姿态，因此暂不作为首页主展示。踢球主展示使用的是单独固定条件回放，并截取了完成踢球后的稳定收势段。

下表里的“轮数”是最终 checkpoint 的 iteration；“回放”表示该 checkpoint 已经被离屏脚本加载并生成视频。`ok` 是工程验收状态，不代表在所有随机地形、所有速度和真机上都稳定。

| 模式 | 任务 ID | checkpoint | 回放 |
| --- | --- | ---: | :---: |
| 平地走路 | `Velocity-Flat` | 3000 | ✅ |
| 粗糙地面走路 | `Velocity-Rough` | 3000 | ✅ |
| 平地速度 + 起立 | `VelStand-Flat` | 2500 | ✅ |
| 粗糙地面速度 + 起立 | `VelStand-Rough` | 2500 | ✅ |
| 平地起身 | `StandUp-Flat` | 4000 | ✅ |
| 粗糙地面起身 | `StandUp-Rough` | 4000 | ✅ |
| 平地坐下 / 起立 | `SitStand-Flat` | 2500 | ✅ |
| 粗糙地面坐下 / 起立 | `SitStand-Rough` | 2500 | ✅ |
| 平地拾取 | `GroundPick-Flat` | 2000 | ✅ |
| 粗糙地面拾取 | `GroundPick-Rough` | 2000 | ✅ |
| 平地踢球 | `BallKick-Flat` | 1500 | ✅ |
| 轮式速度 | `Roller-Velocity` | 5000 | ✅ |
| 轮式转向 / Swizzle | `Roller-Swizzle` | 3000 | ✅ |
| 轮式蹲伏 | `Roller-Crouch` | 1500 | ✅ |
| 轮式坡面 | `Roller-Slope` | 1500 | ✅ |
| 轮式起身 | `Roller-StandUp` | 4000 | ✅ |
| 原地旋转 | `Spin` | 3000 | ✅ |
| 翻滚 | `Roulade` | 6000 | ✅ |

其余训练 case 的 checkpoint 和日志仍可按训练脚本复现；教程仓库只保留精选的三段 GIF/MP4，避免把未通过画面验收的素材继续作为结果传播。


## 实验中的新动作：奶龙大笑

这个动作需要手臂参与：先双手捧腹、身体前仰大笑，再向后倒，随后左手左腿、右手右腿交替敲击地面，最后回到抱腹姿态。原始 MicroDuck 模型只有腿部和头部的 14 个舵机，因此我为这个实验动作增加了左右肩、左右肘四个手臂关节，以及手掌碰撞几何。

![MicroDuck 奶龙大笑动作参考轨迹](./figs/experimental/laugh_choreo_reference.gif)

[下载奶龙大笑动作参考 MP4](./figs/experimental/laugh_choreo_reference.mp4)

这段视频是按同一组动作关键帧生成的稳定参考轨迹，用来确认动作设计和镜头效果；带手臂的 PPO 策略仍在训练和验收中，暂不计入上面的三个正式结果。当前模型没有独立下颌舵机，所以视频里的“大笑”由捧腹、身体后仰、头部动作和交替敲地表达，嘴部开合需要后续加入真实的 jaw actuator。


## 历史批量脚本的使用条件

`train_stable_matrix_stage1.sh` 和 `train_stable_matrix_stage2.sh` 用于已有实验的续训，依赖指定目录中的历史 checkpoint，不是全新克隆仓库后的入门命令。首次练习请使用主教程里的单任务从零训练流程。

## 环境参考

历史实验使用 Python 3.12、mjlab 1.3.0、Warp 1.12.0、PyTorch 2.7.1+cu126；依赖以代码目录的 `pyproject.toml` 和 `uv.lock` 为准。历史正式训练使用8张RTX 4090，这是实验资源配置，不是本教程单任务练习的最低要求。驱动兼容性、显存及吞吐需在自己的机器上通过短训练检查。

## 上游与许可

- 上游：[pollen-robotics/microduck_rl](https://github.com/pollen-robotics/microduck_rl)。本项目历史集成基线为 `develop` 的 `d424a0c`。
- 代码 Apache-2.0；3D 模型按上游说明使用 CC BY-SA-NC，复用时分别检查对应许可。
