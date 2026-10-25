import React, {useState} from 'react';
import styles from './styles.module.css';
import standup from '@site/docs/practices/humanoid/microduck-rl/figs/focus-final/roller_standup_final.mp4';
import turn from '@site/docs/practices/humanoid/microduck-rl/figs/focus-final/roller_swizzle_final.mp4';
import kick from '@site/docs/practices/humanoid/microduck-rl/figs/focus-final/ballkick_final.mp4';
import standupPoster from '@site/docs/practices/humanoid/microduck-rl/figs/focus-final/roller_standup_poster.webp';
import turnPoster from '@site/docs/practices/humanoid/microduck-rl/figs/focus-final/roller_swizzle_poster.webp';
import kickPoster from '@site/docs/practices/humanoid/microduck-rl/figs/focus-final/ballkick_poster.webp';

const clips = [
  {title: '跌倒了，再站起来', src: standup, poster: standupPoster, text: '轮式小黄鸭从趴地状态起身，随后保持站立。', question: '起身成功，是身体离地就够了吗？', answer: '还要观察能否保持站立。只检查瞬间高度，可能把弹起后再次摔倒也算作成功。'},
  {title: '换个方向出发', src: turn, poster: turnPoster, text: '轮式小黄鸭完成转向，并保持身体平衡。', question: '转得越快，就一定越好吗？', answer: '要同时看方向是否到位、身体是否稳定。速度只是目标的一部分。'},
  {title: '踢出去，也要站得住', src: kick, poster: kickPoster, text: '小黄鸭抬脚触球，随后收势。片段在后续环境重置前结束。', question: '如果只给球的位移加分，会发生什么？', answer: '策略可能找到撞球、扑球等捷径。是否会发生，需要实际训练检验；设计奖励时要把完成动作后的状态也考虑进去。'},
];

export function ActionGallery() {
  return <div className={styles.gallery}>{clips.map(clip => <article className={styles.card} key={clip.title}>
    <h3>{clip.title}</h3>
    <video controls playsInline preload="none" poster={clip.poster} aria-label={clip.title}>
      <source src={clip.src} type="video/mp4" />
      你的浏览器不支持视频播放，请使用下方 MP4 链接。
    </video>
    <p>{clip.text}</p>
    <details><summary>{clip.question}</summary><p>{clip.answer}</p></details>
    <a href={clip.src}>打开 MP4</a>
  </article>)}</div>;
}

const steps = [
  ['读到身体状态', '策略收到关节角度、关节速度、身体姿态相关观测，以及目标命令。就像先判断“我现在站得怎么样、要往哪里走”。', '观测 o → 策略输入'],
  ['试一个动作', '策略网络输出关节目标位置。此时是在使用当前网络，并没有每走一步就训练一次网络。', '策略 π(o) → 动作 a'],
  ['让物理世界回应', '执行器模型把目标转成运动，仿真计算接触、速度和新的姿态。动作不一定成功，小黄鸭也可能失去平衡。', '仿真推进 → 新状态'],
  ['给这次尝试打分', '环境按任务计算奖励，并检查是否需要结束这一局。得到奖励并不代表动作一定符合人的期待。', '保存观测、动作、奖励等经验'],
  ['攒经验，再更新', '多个环境重复前面的步骤。收集一批经验后，PPO执行若干轮优化，让带来更好长期回报的动作更可能出现，再继续采样。', '采样一批 → PPO更新 → 继续尝试'],
];

export function TrainingLoop() {
  const [step, setStep] = useState(0);
  return <section className={styles.panel} aria-label="训练闭环互动">
    <p className={styles.eyebrow}>点一下，跟着一次尝试往前走 · 概念演示</p>
    <div className={styles.steps}>{steps.map(([name], i) => <button type="button" key={name}
      aria-pressed={step === i} onClick={() => setStep(i)}>{i + 1}. {name}</button>)}</div>
    <div className={styles.explanation} aria-live="polite" aria-atomic="true">
      <h3>{steps[step][0]}</h3><p>{steps[step][1]}</p><strong>{steps[step][2]}</strong>
    </div>
    <button type="button" className="button button--primary" onClick={() => setStep((step + 1) % steps.length)}>
      {step === steps.length - 1 ? '开始下一轮' : '下一步 →'}
    </button>
  </section>;
}

// Invented, dimensionless scores for teaching reward trade-offs, not rollout measurements.
const candidates = [
  {name: '站着不动', progress: 0, stable: 1, cost: 0},
  {name: '踢球后站稳', progress: 0.7, stable: 1, cost: 0.3},
  {name: '扑向球后倒地', progress: 1, stable: 0, cost: 0.8},
];

export function RewardLab() {
  const [balance, setBalance] = useState(0);
  const [effort, setEffort] = useState(0);
  const scores = candidates.map(c => ({...c, score: c.progress + balance * c.stable - effort * c.cost}));
  const best = Math.max(...scores.map(c => c.score));
  const winners = scores.filter(c => Math.abs(c.score - best) < 1e-8).map(c => c.name).join('、');
  return <section className={styles.panel} aria-label="奖励设计实验">
    <p className={styles.eyebrow}>你来当奖励设计师 · 合成数据算分，不运行物理仿真或 PPO</p>
    <p>三个假想结果，谁的分数最高？先只奖励球的位移，再逐渐加入站稳奖励和动作代价。</p>
    <label className={styles.slider}>站稳奖励权重：{balance.toFixed(1)}
      <input aria-label="站稳奖励权重" type="range" min="0" max="2" step="0.1" value={balance} onChange={e => setBalance(Number(e.target.value))} />
    </label>
    <label className={styles.slider}>动作代价权重：{effort.toFixed(1)}
      <input aria-label="动作代价权重" type="range" min="0" max="3" step="0.1" value={effort} onChange={e => setEffort(Number(e.target.value))} />
    </label>
    <p><code>得分 = 位移分 + 站稳权重 × 站稳分 − 代价权重 × 动作代价</code></p>
    <div className={styles.tableWrap}><table>
      <caption>假想结果的归一化分数（为教学设定，不是实测值）</caption>
      <thead><tr><th>结果</th><th>位移分</th><th>站稳分</th><th>动作代价</th><th>总分</th></tr></thead>
      <tbody>{scores.map(c => <tr key={c.name}><th scope="row">{c.name}</th><td>{c.progress}</td><td>{c.stable}</td><td>{c.cost}</td><td>{c.score.toFixed(2)}</td></tr>)}</tbody>
    </table></div>
    <p role="status">当前最高分：<strong>{winners}</strong>。这是评分偏好，不保证训练一定学出该行为。</p>
    <details><summary>为什么代价过大时，小黄鸭可能不想动？</summary>
      <p>动作带来的收益抵不过惩罚时，不动也可能获得更高分。试试把站稳权重调到 1、动作代价调到 3。真实任务还要考虑整段轨迹的回报和终止条件。</p>
    </details>
    <button type="button" className="button button--secondary" onClick={() => {setBalance(0); setEffort(0);}}>重置：只奖励球的位移</button>
  </section>;
}
