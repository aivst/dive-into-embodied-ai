import React, {useEffect, useRef, useState} from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';
import {Play, Pause, Square, RotateCcw} from 'lucide-react';
import type {createScene, Snapshot} from './scene';
import styles from './styles.module.css';

export default function QuaddleSimulator() {
  const assetBase = useBaseUrl('/quaddle/');
  const host = useRef<HTMLDivElement>(null);
  const section = useRef<HTMLElement>(null);
  const worker = useRef<Worker | null>(null);
  const scene = useRef<ReturnType<typeof createScene> | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [error, setError] = useState('');
  const [state, setState] = useState<Snapshot | null>(null);
  const [suspended, setSuspended] = useState(false);

  useEffect(() => {
    if (!attempt) return;
    let disposed = false, localWorker: Worker | null = null;
    let localScene: ReturnType<typeof createScene> | null = null;
    let inView = true, lastUi = 0, lastMode = '', lastPaused = false;
    setStatus('loading'); setState(null); setError('');
    const fail = (message: string) => {
      if (disposed) return;
      setError(message); setStatus('error');
      localWorker?.terminate();
    };
    const visibility = () => {
      const visible = inView && !document.hidden;
      setSuspended(!visible);
      localWorker?.postMessage({type: 'visibility', value: visible});
      localScene?.setVisible(visible);
    };
    const observer = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; visibility(); });
    if (section.current) observer.observe(section.current);
    document.addEventListener('visibilitychange', visibility);
    import('./scene').then(({createScene}) => {
      if (disposed || !host.current) return;
      localScene = createScene(host.current, () => fail('图形上下文已中断，请重新加载仿真。'));
      scene.current = localScene;
      localWorker = new Worker(`${assetBase}worker.mjs`, {type: 'module'});
      worker.current = localWorker;
      localWorker.onerror = event => fail(event.message || '仿真加载失败，请检查网络或浏览器是否支持 WebAssembly 和 WebGL。');
      localWorker.onmessage = ({data}) => {
        try {
          if (disposed) return;
          if (data.type === 'error') { fail(data.message); return; }
          if (data.type === 'ready') {
            localScene!.load(data.geometry);
            setStatus('ready'); visibility();
          }
          if (data.type === 'state') {
            localScene!.update(data);
            const now = performance.now();
            if (now - lastUi > 150 || data.time === 0 || data.mode !== lastMode || data.paused !== lastPaused) {
              setState(data); lastUi = now; lastMode = data.mode; lastPaused = data.paused;
            }
          }
        } catch (reason) { fail(String(reason)); }
      };
      visibility();
    }).catch(reason => fail(String(reason)));
    return () => {
      disposed = true; observer.disconnect(); document.removeEventListener('visibilitychange', visibility);
      localWorker?.terminate(); localScene?.dispose(); worker.current = null; scene.current = null;
    };
  }, [attempt, assetBase]);

  const ready = status === 'ready';
  const mode = state?.paused ? '物理已暂停' : state?.mode === 'walk' ? '行走中' : '站立 · 物理仍在运行';
  return (
    <section ref={section} className={styles.simulator} aria-label="Quaddle 在线仿真">
      <header className={styles.header}>
        <div><span className={styles.eyebrow}>MUJOCO · 实时交互</span><strong>让 Quaddle 走起来</strong></div>
        <span className={styles.badge}>周期步态控制</span>
      </header>
      <div className={styles.stage}>
        <div ref={host} className={styles.canvas} />
        {status !== 'ready' && <div className={styles.cover}>
          <strong>{status === 'loading' ? '正在加载物理引擎与 Quaddle 模型…' : status === 'error' ? '暂时无法运行仿真' : '在浏览器里运行真正的物理仿真'}</strong>
          <p>{status === 'error' ? error : '四个舵机、被动连杆和地面接触，共同决定它的运动。'}</p>
          {status !== 'loading' && <button type="button" onClick={() => setAttempt(value => value + 1)}>{status === 'error' ? '重新加载' : '加载在线仿真'}</button>}
          {status === 'idle' && <small>首次需下载约 20 MB，无需安装 Python。</small>}
        </div>}
        {ready && <div className={styles.hint}>拖动旋转 · 滚轮缩放 · 相机跟随</div>}
      </div>
      <div className={styles.controls} role="group" aria-label="仿真控制">
        <button type="button" disabled={!ready} aria-pressed={ready && state?.mode === 'walk' && !state?.paused} onClick={() => worker.current?.postMessage({type: 'mode', mode: 'walk'})}><Play size={16} aria-hidden="true" />行走</button>
        <button type="button" disabled={!ready} aria-pressed={ready && state?.mode === 'stand' && !state?.paused} onClick={() => worker.current?.postMessage({type: 'mode', mode: 'stand'})}><Square size={16} aria-hidden="true" />停止并站立</button>
        <button type="button" disabled={!ready} aria-pressed={!!state?.paused} onClick={() => worker.current?.postMessage({type: 'pause', value: !state?.paused})}><Pause size={16} aria-hidden="true" />{state?.paused ? '继续仿真' : '暂停物理'}</button>
        <button type="button" disabled={!ready} onClick={() => {worker.current?.postMessage({type: 'reset'}); scene.current?.resetView();}}><RotateCcw size={16} aria-hidden="true" />重置</button>
        <button type="button" disabled={!ready} onClick={() => scene.current?.resetView()}>复位视角</button>
      </div>
      <p className={styles.status} role="status">{ready ? suspended ? '离开画面时自动挂起，返回后继续。' : mode : '加载后可控制行走、停止、暂停与重置。'}</p>
      <dl className={styles.metrics} aria-label="仿真状态">
        <div><dt>仿真时间</dt><dd>{(state?.time ?? 0).toFixed(1)} s</dd></div>
        <div><dt>前进距离</dt><dd>{(-(state?.position[1] ?? 0)).toFixed(2)} m</dd></div>
        <div><dt>水平速度</dt><dd>{(state?.speed ?? 0).toFixed(3)} m/s</dd></div>
      </dl>
      <p className={styles.caption}>“停止并站立”会平滑收回步态，物理继续计算；“暂停物理”会冻结仿真时间。当前使用参数化控制器，尚未接入强化学习策略。</p>
    </section>
  );
}
